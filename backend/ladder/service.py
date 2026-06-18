"""Ladder service — Submissions, self-validation, episodes, and rating updates.

A *Submission* is an AI agent on the skill ladder. On creation it must pass a
**validation game** (the agent vs a copy of itself); only then does it join the
pool with mu0 = 600. The **Run Episodes** job repeatedly pairs active
submissions — preferring similar ratings, and giving *new* submissions more
games for faster feedback — plays them on rotating decks, and updates both
ratings with the TrueSkill-style rule in ``ladder.rating``.

Background work (validation, episode runs) uses its own DB session per thread.
"""
from __future__ import annotations

import random
import threading
import traceback
import uuid
from datetime import datetime

from agents.registry import make_agent, REGISTRY
from data.cards_db import DECKS
from db.database import SessionLocal
from db.models import Submission, RatingPoint, Episode
from engine.game import GameEngine
from .rating import Rating, update_1v1, expected_score, MU0, SIGMA0

MAX_ACTIVE = 10            # focus on up to 10 agents
NEW_BOOST_GAMES = 20       # below this many games a submission is "new"
NEW_BOOST = 6.0            # selection-weight multiplier for new submissions
TURN_CAP = 220

# in-memory job registry for episode runs (progress polling)
EPISODE_JOBS: dict[str, dict] = {}


# --------------------------------------------------------------------------- #
# Serialization
# --------------------------------------------------------------------------- #
def submission_dict(s: Submission) -> dict:
    r = Rating(s.mu, s.sigma)
    return {
        "id": s.id, "name": s.name, "agent_id": s.agent_id, "deck": s.deck,
        "mu": round(s.mu, 1), "sigma": round(s.sigma, 1),
        "conservative": round(r.conservative, 1),
        "games": s.games, "wins": s.wins, "losses": s.losses, "draws": s.draws,
        "status": s.status, "error_log": s.error_log,
        "is_new": s.games < NEW_BOOST_GAMES and s.status == "active",
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


# --------------------------------------------------------------------------- #
# Match primitives
# --------------------------------------------------------------------------- #
def _deck_for(sub: Submission, rng: random.Random) -> str:
    if sub.deck and sub.deck != "rotating" and sub.deck in DECKS:
        return sub.deck
    return rng.choice(list(DECKS.keys()))


def _play(agent_a_id: str, agent_b_id: str, deck_a: str, deck_b: str,
          ckpt: str, seed: int) -> tuple[str, int]:
    """Play one game; return (result in {'a','b','draw'}, turns)."""
    eng = GameEngine.new_game(DECKS[deck_a](), DECKS[deck_b](),
                              names=(agent_a_id, agent_b_id), seed=seed)
    ag = [make_agent(agent_a_id, ckpt), make_agent(agent_b_id, ckpt)]
    steps = 0
    while not eng.state.is_over() and eng.state.turn_number <= TURN_CAP and steps < 30000:
        eng.apply(ag[eng.state.current_player].select(eng))
        steps += 1
    w = eng.state.winner
    if w is None:
        return "draw", eng.state.turn_number
    return ("a" if w == 0 else "b"), eng.state.turn_number


# --------------------------------------------------------------------------- #
# Validation (self-mirror)
# --------------------------------------------------------------------------- #
def validate_submission(submission_id: int, ckpt: str) -> None:
    """Run the agent against a copy of itself; activate or mark error."""
    db = SessionLocal()
    try:
        s = db.get(Submission, submission_id)
        if not s:
            return
        try:
            deck = _deck_for(s, random.Random(submission_id))
            result, turns = _play(s.agent_id, s.agent_id, deck, deck, ckpt,
                                  seed=1000 + submission_id)
            # A finished mirror game is a pass.
            s.status = "active"
            s.mu, s.sigma = MU0, SIGMA0
            s.error_log = ""
            db.add(RatingPoint(submission_id=s.id, games=0, mu=MU0, sigma=SIGMA0))
        except Exception:
            s.status = "error"
            s.error_log = (
                f"Validation game failed for agent '{s.agent_id}' on deck "
                f"'{s.deck}':\n\n" + traceback.format_exc()
            )
        db.commit()
    finally:
        db.close()


# --------------------------------------------------------------------------- #
# Submission creation
# --------------------------------------------------------------------------- #
def create_submission(name: str, agent_id: str, deck: str, owner_id, ckpt: str) -> dict:
    if agent_id not in REGISTRY:
        raise ValueError(f"unknown agent '{agent_id}'")
    if deck != "rotating" and deck not in DECKS:
        raise ValueError(f"unknown deck '{deck}'")
    db = SessionLocal()
    try:
        active = db.query(Submission).filter(
            Submission.status.in_(["active", "validating"])).count()
        if active >= MAX_ACTIVE:
            raise ValueError(
                f"submission pool is full ({MAX_ACTIVE} max) — delete one first")
        s = Submission(name=name.strip()[:80] or agent_id, agent_id=agent_id,
                       deck=deck, owner_id=owner_id, mu=MU0, sigma=SIGMA0,
                       status="validating")
        db.add(s)
        db.commit()
        sid = s.id
        out = submission_dict(s)
    finally:
        db.close()
    threading.Thread(target=validate_submission, args=(sid, ckpt), daemon=True).start()
    return out


# --------------------------------------------------------------------------- #
# Matchmaking
# --------------------------------------------------------------------------- #
def _pick_pair(subs: list[Submission], rng: random.Random):
    """Pick (A, B): A weighted toward *new* submissions; B toward similar mu."""
    weights = [NEW_BOOST if s.games < NEW_BOOST_GAMES else 1.0 for s in subs]
    a = rng.choices(subs, weights=weights, k=1)[0]
    others = [s for s in subs if s.id != a.id]
    # closer mu -> higher weight (fair matches)
    ow = [1.0 / (1.0 + abs(a.mu - o.mu) / 100.0) for o in others]
    b = rng.choices(others, weights=ow, k=1)[0]
    return a, b


def _run_episodes_job(job_id: str, count: int, ckpt: str) -> None:
    db = SessionLocal()
    rng = random.Random()
    try:
        job = EPISODE_JOBS[job_id]
        for i in range(count):
            if job.get("cancel"):
                break
            subs = db.query(Submission).filter(Submission.status == "active").all()
            if len(subs) < 2:
                job["error"] = "need at least 2 active submissions"
                break
            a, b = _pick_pair(subs, rng)
            deck_a, deck_b = _deck_for(a, rng), _deck_for(b, rng)
            try:
                result, turns = _play(a.agent_id, b.agent_id, deck_a, deck_b,
                                      ckpt, seed=rng.randint(0, 1 << 30))
            except Exception:
                job["progress"] = i + 1
                continue

            score_a = 1.0 if result == "a" else 0.0 if result == "b" else 0.5
            ra, rb = update_1v1(Rating(a.mu, a.sigma), Rating(b.mu, b.sigma), score_a)
            a.mu, a.sigma, b.mu, b.sigma = ra.mu, ra.sigma, rb.mu, rb.sigma
            a.games += 1; b.games += 1
            if result == "a": a.wins += 1; b.losses += 1
            elif result == "b": b.wins += 1; a.losses += 1
            else: a.draws += 1; b.draws += 1

            db.add(Episode(sub_a_id=a.id, sub_b_id=b.id, deck_a=deck_a,
                           deck_b=deck_b, result=result, turns=turns))
            db.add(RatingPoint(submission_id=a.id, games=a.games, mu=a.mu, sigma=a.sigma))
            db.add(RatingPoint(submission_id=b.id, games=b.games, mu=b.mu, sigma=b.sigma))
            db.commit()
            # lifetime per-model scoreboard (every ladder game counts)
            try:
                from stats.model_stats import record_game
                record_game(a.agent_id, b.agent_id, result)
            except Exception:
                pass
            job["progress"] = i + 1
        job["status"] = "cancelled" if job.get("cancel") else "done"
        job["standings"] = [
            submission_dict(s) for s in
            sorted(db.query(Submission).filter(Submission.status == "active").all(),
                   key=lambda x: Rating(x.mu, x.sigma).conservative, reverse=True)
        ]
    except Exception:
        EPISODE_JOBS[job_id]["status"] = "error"
        EPISODE_JOBS[job_id]["error"] = traceback.format_exc()
    finally:
        db.close()


def start_episode_run(count: int, ckpt: str) -> str:
    job_id = uuid.uuid4().hex[:12]
    EPISODE_JOBS[job_id] = {"status": "running", "progress": 0, "total": count,
                            "cancel": False, "error": None, "standings": []}
    threading.Thread(target=_run_episodes_job, args=(job_id, count, ckpt),
                     daemon=True).start()
    return job_id


def cancel_episode_run(job_id: str) -> dict | None:
    job = EPISODE_JOBS.get(job_id)
    if not job:
        return None
    if job["status"] == "running":
        job["cancel"] = True  # the worker stops at the next episode boundary
    return job


# --------------------------------------------------------------------------- #
# Queries / export
# --------------------------------------------------------------------------- #
def list_submissions() -> list[dict]:
    db = SessionLocal()
    try:
        subs = db.query(Submission).all()
        subs.sort(key=lambda s: (s.status != "active",
                                 -Rating(s.mu, s.sigma).conservative))
        return [submission_dict(s) for s in subs]
    finally:
        db.close()


def submission_detail(submission_id: int) -> dict | None:
    db = SessionLocal()
    try:
        s = db.get(Submission, submission_id)
        if not s:
            return None
        out = submission_dict(s)
        out["history"] = [
            {"games": h.games, "mu": round(h.mu, 1), "sigma": round(h.sigma, 1)}
            for h in sorted(s.history, key=lambda h: (h.games, h.id))
        ]
        eps = db.query(Episode).filter(
            (Episode.sub_a_id == s.id) | (Episode.sub_b_id == s.id)
        ).order_by(Episode.id.desc()).limit(15).all()
        names = {x.id: x.name for x in db.query(Submission).all()}
        out["recent_episodes"] = [{
            "opponent": names.get(e.sub_b_id if e.sub_a_id == s.id else e.sub_a_id, "?"),
            "result": ("win" if (e.result == "a") == (e.sub_a_id == s.id)
                       else "draw" if e.result == "draw" else "loss"),
            "deck": e.deck_a if e.sub_a_id == s.id else e.deck_b,
            "turns": e.turns,
        } for e in eps]
        return out
    finally:
        db.close()


def export_manifest(submission_id: int) -> dict | None:
    """A self-contained description of the agent for the Kaggle submission seam."""
    db = SessionLocal()
    try:
        s = db.get(Submission, submission_id)
        if not s:
            return None
        meta = REGISTRY.get(s.agent_id, {})
        return {
            "submission": s.name,
            "agent": {
                "model": s.agent_id,
                "family": meta.get("family"),
                "label": meta.get("label"),
                "description": meta.get("description"),
            },
            "deck": s.deck,
            "rating": {"mu": round(s.mu, 1), "sigma": round(s.sigma, 1),
                       "conservative": round(Rating(s.mu, s.sigma).conservative, 1)},
            "record": {"games": s.games, "wins": s.wins,
                       "losses": s.losses, "draws": s.draws},
            "entrypoint": "backend/competition/agent_entry.py",
            "usage": ("Set AGENT_MODEL to this model id (and pin the deck) in the "
                      "competition agent entrypoint, then bind decode/encode to the "
                      "official starter env."),
            "exported_at": datetime.utcnow().isoformat(),
        }
    finally:
        db.close()
