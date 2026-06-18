"""FastAPI backend.

Exposes the engine + agents over HTTP for the three UI modes:
  * Watch AI vs AI  -> POST /api/game/new (mode=ai_vs_ai), then /step
  * Play vs AI       -> POST /api/game/new (mode=human_vs_ai), then /action
  * Training dash     -> GET /api/training/metrics

Game sessions are held in memory (fine for a single-instance demo / Render
service). Hidden information is masked per-viewer in serialisation.
"""
from __future__ import annotations

import os
import sys
import uuid
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from engine.game import GameEngine
from engine.actions import Action, ActionType
from data.cards_db import DECKS
from data import card_api
from data import deck_import
from db.database import get_db, init_db
from db.models import User, GameRecord
from db.seed import seed_admin
from auth.routes import router as auth_router, current_user

import math as _math
from starlette.responses import JSONResponse as _JSONResponse


def _finite(o):
    """Recursively replace NaN/Infinity with null so a diverged training run
    (or any stray non-finite float) can't make a response fail to serialize."""
    if isinstance(o, float):
        return o if _math.isfinite(o) else None
    if isinstance(o, dict):
        return {k: _finite(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_finite(v) for v in o]
    return o


class SafeJSONResponse(_JSONResponse):
    def render(self, content) -> bytes:  # type: ignore[override]
        return super().render(_finite(content))


app = FastAPI(title="Pokémon TCG AI Arena", version="1.0",
              default_response_class=SafeJSONResponse)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)
app.include_router(auth_router)


@app.on_event("startup")
def _startup() -> None:
    init_db()
    try:
        seed_admin()
    except Exception as exc:  # don't crash the server if the DB is briefly unavailable
        print(f"[startup] admin seed skipped: {exc}")
    try:
        _load_image_overrides()
    except Exception as exc:
        print(f"[startup] image overrides skipped: {exc}")


# card_id -> replacement image URL, cached in memory and applied on serialization
IMAGE_OVERRIDES: dict[str, str] = {}


def _load_image_overrides() -> None:
    from db.database import SessionLocal
    from db.models import CardImageOverride
    db = SessionLocal()
    try:
        IMAGE_OVERRIDES.clear()
        for row in db.query(CardImageOverride).all():
            IMAGE_OVERRIDES[row.card_id] = row.image_url
    finally:
        db.close()


def _img(card_id, image):
    return IMAGE_OVERRIDES.get(card_id, image)

_BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CKPT = os.environ.get(
    "RL_CHECKPOINT",
    os.path.join(_BACKEND_ROOT, "checkpoints", "policy_latest.pt"),
)


def _make_agent(kind: str):
    from agents.registry import make_agent
    return make_agent(kind, CKPT)


class Session:
    def __init__(self, engine: GameEngine, mode: str, agents: dict,
                 human_seat: Optional[int], model_ids: Optional[dict] = None):
        self.engine = engine
        self.mode = mode
        self.agents = agents          # seat -> agent (for AI seats)
        self.human_seat = human_seat
        self.model_ids = model_ids or {}   # seat -> model id string
        self.recorded = False         # ensure we score the game only once


def _record_session_result(sess: "Session") -> None:
    """Record the finished game into the lifetime model scoreboard (once)."""
    if sess.recorded or not sess.engine.state.is_over():
        return
    sess.recorded = True
    try:
        from stats.model_stats import record_game, record_single
        winner = sess.engine.state.winner  # 0, 1, or None
        if sess.mode == "ai_vs_ai":
            result = "a" if winner == 0 else "b" if winner == 1 else "draw"
            record_game(sess.model_ids.get(0), sess.model_ids.get(1), result)
        else:
            # human vs AI: score only the AI seat, from its perspective
            ai_seat = next(iter(sess.agents), None)
            if ai_seat is not None:
                outcome = ("draw" if winner is None
                           else "win" if winner == ai_seat else "loss")
                record_single(sess.model_ids.get(ai_seat), outcome)
    except Exception:
        pass  # scoreboard must never break gameplay


SESSIONS: dict[str, Session] = {}

# Imported decks live in-memory for the running backend, keyed by a deck id.
# Each entry is (display_name, list[CardDef]).
CUSTOM_DECKS: dict[str, tuple] = {}


def _resolve_deck(name: str):
    """Resolve a deck id to a fresh card list (built-in or imported)."""
    if name in DECKS:
        return DECKS[name]()
    if name in CUSTOM_DECKS:
        return list(CUSTOM_DECKS[name][1])
    raise HTTPException(400, f"unknown deck '{name}'")


class NewGame(BaseModel):
    mode: str = "ai_vs_ai"            # "ai_vs_ai" | "human_vs_ai"
    deck_a: str = "charizard_ex"
    deck_b: str = "gardevoir_ex"
    agent_a: str = "heuristic"        # used for AI seats
    agent_b: str = "mcts"
    human_seat: int = 0              # for human_vs_ai
    seed: Optional[int] = None


class ActionReq(BaseModel):
    index: int                       # index into current legal_actions


@app.get("/api/health")
def health():
    return {"ok": True, "checkpoint_loaded": os.path.exists(CKPT)}


@app.get("/api/decks")
def decks():
    from data.cards_db import deck_catalog
    custom = [{"id": k, "name": v[0], "custom": True} for k, v in CUSTOM_DECKS.items()]
    return {
        "decks": list(DECKS.keys()) + list(CUSTOM_DECKS.keys()),
        "builtin": list(DECKS.keys()),
        "custom": custom,
        "meta": deck_catalog(),
    }


@app.get("/api/sets")
def sets():
    """Built-in expansions represented in the card pool (with counts)."""
    from data.cards_db import builtin_sets
    return {"sets": builtin_sets()}


class DeckImportReq(BaseModel):
    name: str = "Imported deck"
    list: str


@app.post("/api/decks/import")
def import_deck(req: DeckImportReq):
    """Parse a pasted decklist, validate it against the implemented card pool,
    and (if valid) register it so it can be selected in any game."""
    parsed = deck_import.parse_decklist(req.list)
    result = {
        "ok": parsed.ok,
        "total": parsed.total,
        "counts": parsed.counts,
        "unknown": parsed.unknown,
        "errors": parsed.errors,
        "warnings": parsed.warnings,
    }
    if not parsed.ok:
        return result
    import re as _re
    slug = _re.sub(r"[^a-z0-9]+", "_", req.name.lower()).strip("_") or "deck"
    deck_id = f"custom_{slug}_{uuid.uuid4().hex[:6]}"
    CUSTOM_DECKS[deck_id] = (req.name, parsed.cards)
    result["deck_id"] = deck_id
    result["name"] = req.name
    return result


@app.get("/api/cards/catalog")
def cards_catalog():
    """Battle-ready cards the importer recognises, plus a ready-to-paste sample."""
    from data.cards_db import charizard_deck
    from data.cards_db import (
        CHARMANDER, CHARMELEON, CHARIZARD_EX, PIDGEY, PIDGEOT_EX,
        PROFESSORS_RESEARCH, BOSS_ORDERS, ULTRA_BALL, SWITCH, POTION,
        FIRE_ENERGY, DOUBLE_TURBO,
    )
    sample = deck_import.render_decklist([
        (CHARMANDER, 4), (CHARMELEON, 2), (CHARIZARD_EX, 3),
        (PIDGEY, 3), (PIDGEOT_EX, 2),
        (PROFESSORS_RESEARCH, 4), (BOSS_ORDERS, 3), (ULTRA_BALL, 4),
        (SWITCH, 2), (POTION, 2), (FIRE_ENERGY, 24), (DOUBLE_TURBO, 7),
    ])
    return {"cards": deck_import.battle_ready_cards(), "sample_decklist": sample}


@app.get("/api/agents")
def agents():
    from agents.registry import list_agents
    return {"agents": [a["id"] for a in list_agents()], "models": list_agents()}


@app.post("/api/game/new")
def new_game(req: NewGame):
    import random
    seed = req.seed if req.seed is not None else random.randint(0, 2**31 - 1)
    deck_a_cards = _resolve_deck(req.deck_a)
    deck_b_cards = _resolve_deck(req.deck_b)
    engine = GameEngine.new_game(
        deck_a_cards, deck_b_cards,
        names=(req.deck_a, req.deck_b), seed=seed,
    )
    if req.mode == "human_vs_ai":
        ai_seat = 1 - req.human_seat
        agents = {ai_seat: _make_agent(req.agent_b)}
        human_seat = req.human_seat
        model_ids = {ai_seat: req.agent_b}
    else:
        agents = {0: _make_agent(req.agent_a), 1: _make_agent(req.agent_b)}
        human_seat = None
        model_ids = {0: req.agent_a, 1: req.agent_b}
    gid = uuid.uuid4().hex[:12]
    SESSIONS[gid] = Session(engine, req.mode, agents, human_seat, model_ids)
    if req.mode == "human_vs_ai":
        _advance_ai_until_human(SESSIONS[gid])
        _record_session_result(SESSIONS[gid])
    return {"game_id": gid, "seed": seed, "state": _view(SESSIONS[gid])}


def _advance_ai_until_human(sess: Session, guard_max: int = 500) -> None:
    """Let AI seats play until it's the human's turn or the game ends.

    Needed because the first player is decided by a coin flip — if the AI goes
    first, the human would otherwise be handed a board with no legal actions.
    """
    eng = sess.engine
    guard = 0
    while (not eng.state.is_over()
           and eng.state.current_player != sess.human_seat
           and guard < guard_max):
        ai = sess.agents.get(eng.state.current_player)
        if ai is None:
            break
        eng.apply(ai.select(eng))
        guard += 1


def _view(sess: Session) -> dict:
    viewer = sess.human_seat  # None -> full view for spectating
    state = sess.engine.state.to_dict(viewer=viewer)
    # apply any user image overrides to the board's Pokémon art
    if IMAGE_OVERRIDES:
        for pl in state.get("players", []):
            for poke in ([pl.get("active")] + (pl.get("bench") or [])):
                if poke and poke.get("card_id") in IMAGE_OVERRIDES:
                    poke["image"] = IMAGE_OVERRIDES[poke["card_id"]]
    state["legal_actions"] = _legal_view(sess)
    return state


def _legal_view(sess: Session) -> list[dict]:
    eng = sess.engine
    if eng.state.is_over():
        return []
    # only expose human's legal actions in human mode when it's their turn
    if sess.human_seat is not None and eng.state.current_player != sess.human_seat:
        return []
    out = []
    for i, a in enumerate(eng.legal_actions()):
        out.append({"index": i, "type": a.type.value, "describe": a.describe(),
                    "label": _label(eng, a)})
    return out


def _label(eng: GameEngine, a: Action) -> str:
    me = eng.state.current
    if a.type == ActionType.ATTACK and me.active:
        atk = me.active.card.attacks[a.sub_index]
        return f"Attack: {atk.name} ({atk.damage})"
    if a.type == ActionType.ATTACH_ENERGY and a.hand_index is not None:
        return f"Attach {me.hand[a.hand_index].card.name}"
    if a.type == ActionType.EVOLVE and a.hand_index is not None:
        return f"Evolve into {me.hand[a.hand_index].card.name}"
    if a.type == ActionType.PLAY_BASIC and a.hand_index is not None:
        return f"Bench {me.hand[a.hand_index].card.name}"
    if a.type in (ActionType.PLAY_SUPPORTER, ActionType.PLAY_ITEM) and a.hand_index is not None:
        return f"Play {me.hand[a.hand_index].card.name}"
    if a.type == ActionType.USE_ABILITY:
        return "Use Ability"
    if a.type == ActionType.RETREAT:
        return "Retreat"
    if a.type == ActionType.END_TURN:
        return "End Turn"
    return a.type.value


@app.get("/api/game/{gid}/state")
def get_state(gid: str):
    sess = SESSIONS.get(gid)
    if not sess:
        raise HTTPException(404, "game not found")
    return _view(sess)


@app.post("/api/game/{gid}/step")
def step(gid: str):
    """Advance an AI-vs-AI game by a single ply."""
    sess = SESSIONS.get(gid)
    if not sess:
        raise HTTPException(404, "game not found")
    eng = sess.engine
    if eng.state.is_over():
        return {"done": True, "state": _view(sess)}
    agent = sess.agents.get(eng.state.current_player)
    if agent is None:
        raise HTTPException(400, "no agent for current seat")
    action = agent.select(eng)
    eng.apply(action)
    _record_session_result(sess)
    return {"done": eng.state.is_over(), "last_action": action.describe(), "state": _view(sess)}


@app.post("/api/game/{gid}/action")
def human_action(gid: str, req: ActionReq):
    """Apply a human action, then let the AI take its full turn."""
    sess = SESSIONS.get(gid)
    if not sess:
        raise HTTPException(404, "game not found")
    eng = sess.engine
    if eng.state.is_over():
        return {"done": True, "state": _view(sess)}
    if eng.state.current_player != sess.human_seat:
        raise HTTPException(400, "not your turn")
    legal = eng.legal_actions()
    if req.index < 0 or req.index >= len(legal):
        raise HTTPException(400, "illegal action index")
    eng.apply(legal[req.index])
    # let the AI play until control returns to the human or the game ends
    _advance_ai_until_human(sess)
    _record_session_result(sess)
    return {"done": eng.state.is_over(), "state": _view(sess)}


@app.get("/api/training/metrics")
def training_metrics():
    import json
    # Look where the trainer actually writes: honour CKPT_DIR (same env var the
    # trainer uses), then the package-relative path, then the CWD. Use isfile so
    # a *directory* named metrics.json (e.g. a stray dir or a volume mount) is
    # reported clearly instead of raising IsADirectoryError on open().
    candidates = []
    if os.environ.get("CKPT_DIR"):
        candidates.append(os.path.join(os.environ["CKPT_DIR"], "metrics.json"))
    candidates.append(os.path.join(_BACKEND_ROOT, "checkpoints", "metrics.json"))
    candidates.append(os.path.join(os.getcwd(), "checkpoints", "metrics.json"))

    found = next((p for p in candidates if os.path.isfile(p)), None)
    if not found:
        dir_hit = next((p for p in candidates if os.path.isdir(p)), None)
        if dir_hit:
            return {"metrics": [], "note": (
                f"'{dir_hit}' is a directory, not a file. Delete it (e.g. "
                f"rmdir '{dir_hit}') — or, if it's a Docker volume mount, remove "
                "that mount — so the trainer can write metrics.json, then re-run "
                "python -m rl.train.")}
        return {"metrics": [], "note": "No training run yet. Run python -m rl.train"}
    try:
        with open(found, encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError:
        return {"metrics": [], "note": "Training metrics file is mid-write — refresh in a moment."}
    except Exception as e:  # never 500 the dashboard; show the real reason
        return {"metrics": [], "note": f"Couldn't read {found}: {e}"}
    return {"metrics": _finite(data)}


@app.get("/api/cards/search")
def cards_search(q: str = "", page: int = 1, standard: bool = True):
    res = card_api.search_cards(q, page=page, standard_only=standard)
    if IMAGE_OVERRIDES:
        for c in res.get("data", []):
            if c.get("id") in IMAGE_OVERRIDES:
                c["image"] = IMAGE_OVERRIDES[c["id"]]
                c["image_overridden"] = True
    return res


@app.get("/api/cards/sets")
def cards_sets():
    return card_api.list_standard_sets()


@app.get("/api/rules")
def rules():
    """The official rules the engine enforces, grouped by phase (the rule feed)."""
    from engine.rules_reference import rules_payload
    return rules_payload()


@app.get("/api/sources")
def sources():
    """Attribution + official reference links. Images are not owned by us."""
    return {
        "disclaimer": (
            "Pokémon and all card and character images are © The Pokémon Company, "
            "Nintendo, Game Freak, and Creatures Inc. We claim no ownership of any "
            "Pokémon imagery or intellectual property; it is shown here for "
            "reference and educational purposes only."
        ),
        "links": [
            {"label": "Official card list (Pokémon.com)",
             "url": "https://www.pokemon.com/us/pokemon-tcg/pokemon-cards"},
            {"label": "Set galleries (Pokémon.com TCG)",
             "url": "https://tcg.pokemon.com/en-us/all-galleries/"},
            {"label": "Set index (Pokellector)",
             "url": "https://www.pokellector.com/sets"},
            {"label": "Pokédex (Pokémon.com)",
             "url": "https://www.pokemon.com/us/pokedex"},
        ],
    }


# --------------------------------------------------------------------------- #
# Model comparison tournaments (background jobs with live progress)
# --------------------------------------------------------------------------- #
import threading

TOURNAMENTS: dict[str, dict] = {}


class TournamentReq(BaseModel):
    agents: list[str]
    decks: list[str]
    games_per_pairing: int = 6


@app.post("/api/tournament/run")
def tournament_run(req: TournamentReq):
    from agents.registry import REGISTRY
    from eval.tournament import run_tournament

    agent_ids = list(dict.fromkeys(req.agents))
    if len(agent_ids) < 2:
        raise HTTPException(400, "pick at least two models to compare")
    for a in agent_ids:
        if a not in REGISTRY:
            raise HTTPException(400, f"unknown model '{a}'")
    if not req.decks:
        raise HTTPException(400, "pick at least one deck")
    for d in req.decks:
        _resolve_deck(d)  # validates existence (raises 400 if unknown)
    games = max(1, min(30, req.games_per_pairing))

    total = (len(agent_ids) * (len(agent_ids) - 1) // 2) * games
    job_id = uuid.uuid4().hex[:12]
    TOURNAMENTS[job_id] = {
        "status": "running", "done": 0, "total": total, "cancel": False,
        "result": None, "error": None,
        "config": {"agents": agent_ids, "decks": req.decks, "games_per_pairing": games},
    }

    def worker():
        try:
            def prog(d, t):
                TOURNAMENTS[job_id]["done"] = d
                TOURNAMENTS[job_id]["total"] = t
            res = run_tournament(
                agent_ids, req.decks, games,
                deck_resolver=_resolve_deck, checkpoint=CKPT, progress=prog,
                should_continue=lambda: not TOURNAMENTS[job_id].get("cancel"),
            )
            TOURNAMENTS[job_id]["result"] = res
            TOURNAMENTS[job_id]["status"] = "cancelled" if res.get("cancelled") else "done"
        except Exception as exc:  # surface to the client, don't crash the server
            TOURNAMENTS[job_id]["status"] = "error"
            TOURNAMENTS[job_id]["error"] = str(exc)

    threading.Thread(target=worker, daemon=True).start()
    return {"job_id": job_id, "total_games": total}


@app.post("/api/tournament/{job_id}/cancel")
def tournament_cancel(job_id: str):
    job = TOURNAMENTS.get(job_id)
    if not job:
        raise HTTPException(404, "tournament not found")
    if job["status"] == "running":
        job["cancel"] = True  # the worker stops at the next game boundary
    return {"job_id": job_id, "status": job["status"], "cancelling": job.get("cancel", False)}


@app.get("/api/tournament/{job_id}")
def tournament_status(job_id: str):
    job = TOURNAMENTS.get(job_id)
    if not job:
        raise HTTPException(404, "tournament not found")
    return job


# --------------------------------------------------------------------------- #
# PTCG AI Battle Challenge (Kaggle) — competition info + strategy report
# --------------------------------------------------------------------------- #
@app.get("/api/competition/info")
def competition_info():
    from agents.registry import list_agents
    from engine.rules_reference import rules_payload
    models = list_agents()
    return {
        "name": "Pokémon Trading Card Game AI Battle Challenge",
        "categories": [
            {"key": "simulation", "label": "Simulation Category",
             "url": "https://www.kaggle.com/competitions/pokemon-tcg-ai-battle",
             "summary": "Submit an AI agent; Kaggle runs continuous automated matches on a live leaderboard. Imperfect-information, Standard format with custom tournament rules. No prize money; required to enter Strategy."},
            {"key": "strategy", "label": "Strategy Category",
             "url": "https://www.kaggle.com/competitions/pokemon-tcg-ai-battle-challenge-strategy",
             "summary": "Submit a report explaining your agent's strategy (deck construction, matchups, originality, analysis). Prize-bearing; strong analysis can win even from mid-leaderboard."},
        ],
        "readiness": [
            {"item": "Rules-faithful engine", "status": "ready",
             "detail": f"{rules_payload()['count']} official rules enforced."},
            {"item": "Imperfect-information agents", "status": "ready",
             "detail": "ISMCTS samples hidden cards; the RL policy uses only the observable encoding."},
            {"item": "Rules-legal decks", "status": "ready",
             "detail": f"{len(DECKS)} archetypes, each validated 60-card / 4-copy."},
            {"item": "Strategy report", "status": "ready",
             "detail": "Generated from live tournament results (Strategy Category)."},
            {"item": "Simulation submission binding", "status": "pending",
             "detail": "Agent entrypoint is built; bind decode/encode to the official starter env to submit."},
        ],
        "models": models,
        "disclaimer": (
            "Unaffiliated with The Pokémon Company / Kaggle. Pokémon imagery is "
            "© The Pokémon Company / Nintendo / Game Freak / Creatures Inc."
        ),
    }


class ReportReq(BaseModel):
    job_id: Optional[str] = None
    agents: list[str] = ["heuristic", "greedy", "minimax", "rl"]
    decks: list[str] = ["charizard_ex", "gardevoir_ex", "miraidon_ex"]
    games_per_pairing: int = 3


# background report jobs (so generation never blocks a request or dies on
# client navigation — the UI polls for the result and can re-attach after a
# tab switch)
REPORT_JOBS: dict[str, dict] = {}


def _run_report_job(job_id: str, agents: list[str], decks: list[str], games: int):
    from eval.tournament import run_tournament
    from competition.strategy_report import generate_report
    import traceback
    try:
        result = run_tournament(agents, decks, games, deck_resolver=_resolve_deck,
                                checkpoint=CKPT, record=False,
                                progress=lambda d, t: REPORT_JOBS[job_id].update(progress=d, total=t))
        REPORT_JOBS[job_id].update(
            status="done", markdown=generate_report(result, decks),
            best=result.get("best"), filename="STRATEGY_REPORT.md")
    except Exception:
        REPORT_JOBS[job_id].update(status="error", error=traceback.format_exc())


@app.post("/api/competition/report")
def competition_report(req: ReportReq):
    """Start a Strategy-Category writeup as a background job; returns a job id.
    Poll GET /api/competition/report/{job_id} for the result."""
    import threading
    for d in req.decks:
        _resolve_deck(d)  # validate up front (raises 4xx if unknown)
    games = max(1, min(6, req.games_per_pairing))
    job_id = uuid.uuid4().hex[:12]
    REPORT_JOBS[job_id] = {"status": "running", "progress": 0, "total": 0,
                           "markdown": None, "best": None, "error": None}
    threading.Thread(target=_run_report_job,
                     args=(job_id, req.agents, req.decks, games), daemon=True).start()
    return {"job_id": job_id, "status": "running"}


@app.get("/api/competition/report/{job_id}")
def competition_report_status(job_id: str):
    job = REPORT_JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "report job not found")
    return job


# --------------------------------------------------------------------------- #
# Skill-rating ladder — Submissions & Episodes
# --------------------------------------------------------------------------- #
class SubmissionReq(BaseModel):
    name: str
    agent: str
    deck: str = "rotating"


class EpisodeRunReq(BaseModel):
    count: int = 30


@app.post("/api/submissions")
def create_submission_ep(req: SubmissionReq):
    from ladder.service import create_submission
    try:
        return create_submission(req.name, req.agent, req.deck, None, CKPT)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/submissions")
def list_submissions_ep():
    from ladder.service import list_submissions, MAX_ACTIVE
    return {"submissions": list_submissions(), "max_active": MAX_ACTIVE}


@app.get("/api/submissions/{submission_id}")
def submission_detail_ep(submission_id: int):
    from ladder.service import submission_detail
    d = submission_detail(submission_id)
    if not d:
        raise HTTPException(404, "submission not found")
    return d


@app.get("/api/submissions/{submission_id}/export")
def submission_export_ep(submission_id: int):
    from ladder.service import export_manifest
    m = export_manifest(submission_id)
    if not m:
        raise HTTPException(404, "submission not found")
    return m


@app.delete("/api/submissions/{submission_id}")
def delete_submission_ep(submission_id: int, db=Depends(get_db)):
    from db.models import Submission, RatingPoint, Episode
    s = db.get(Submission, submission_id)
    if not s:
        raise HTTPException(404, "submission not found")
    db.query(RatingPoint).filter(RatingPoint.submission_id == submission_id).delete()
    db.query(Episode).filter(
        (Episode.sub_a_id == submission_id) | (Episode.sub_b_id == submission_id)
    ).delete()
    db.delete(s)
    db.commit()
    return {"deleted": submission_id}


@app.post("/api/episodes/run")
def run_episodes_ep(req: EpisodeRunReq):
    from ladder.service import start_episode_run
    count = max(1, min(200, req.count))
    return {"job_id": start_episode_run(count, CKPT)}


@app.get("/api/episodes/status/{job_id}")
def episodes_status_ep(job_id: str):
    from ladder.service import EPISODE_JOBS
    job = EPISODE_JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "job not found")
    return job


@app.post("/api/episodes/{job_id}/cancel")
def episodes_cancel_ep(job_id: str):
    from ladder.service import cancel_episode_run
    job = cancel_episode_run(job_id)
    if not job:
        raise HTTPException(404, "job not found")
    return {"job_id": job_id, "status": job["status"], "cancelling": job.get("cancel", False)}


# --------------------------------------------------------------------------- #
# Lifetime model scoreboard (every game involving a model is recorded)
# --------------------------------------------------------------------------- #
@app.get("/api/models/stats")
def model_stats_ep():
    from stats.model_stats import list_stats
    return {"stats": list_stats()}


@app.get("/api/models/stats/export")
def model_stats_export_ep(format: str = "json"):
    from stats.model_stats import list_stats, export_csv
    if format == "csv":
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse(
            export_csv(),
            headers={"Content-Disposition": "attachment; filename=model_scores.csv"},
        )
    from datetime import datetime, timezone
    return {"stats": list_stats(),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "filename": "model_scores.json"}


@app.post("/api/models/stats/reset")
def model_stats_reset_ep():
    from stats.model_stats import reset_stats
    return {"reset": reset_stats()}


# --------------------------------------------------------------------------- #
# Model explainer + easy export
# --------------------------------------------------------------------------- #
@app.get("/api/models/docs")
def model_docs_ep():
    from agents.model_docs import model_docs
    return {"models": model_docs()}


def _model_manifest(model_id: str) -> dict:
    from agents.model_docs import model_doc
    from stats.model_stats import list_stats
    doc = model_doc(model_id)
    if not doc:
        raise HTTPException(404, "unknown model")
    score = next((s for s in list_stats() if s["model_id"] == model_id), None)
    return {
        "model": model_id,
        "label": doc["label"],
        "family": doc["family"],
        "summary": doc["summary"],
        "rationale": doc["why"],
        "how_it_works": doc["how"],
        "parameters": doc["params"],
        "imperfect_info": doc["imperfect_info"],
        "lifetime_score": score,
        "entrypoint": "backend/competition/agent_entry.py",
        "usage": "Set AGENT_MODEL to this model id in the competition agent entrypoint.",
    }


@app.get("/api/models/{model_id}/export")
def model_export_ep(model_id: str):
    return _model_manifest(model_id)


@app.get("/api/models/export")
def models_export_all_ep():
    from agents.registry import REGISTRY
    from datetime import datetime, timezone
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "models": [_model_manifest(mid) for mid in REGISTRY],
    }


class CardImageReq(BaseModel):
    url: str


@app.post("/api/cards/{card_id}/image")
def set_card_image_ep(card_id: str, req: CardImageReq, db=Depends(get_db)):
    from db.models import CardImageOverride
    url = (req.url or "").strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        raise HTTPException(400, "image URL must start with http:// or https://")
    row = db.query(CardImageOverride).filter(
        CardImageOverride.card_id == card_id).one_or_none()
    if row is None:
        row = CardImageOverride(card_id=card_id, image_url=url)
        db.add(row)
    else:
        row.image_url = url
    db.commit()
    IMAGE_OVERRIDES[card_id] = url           # update in-memory cache
    return {"card_id": card_id, "image": url}


@app.delete("/api/cards/{card_id}/image")
def clear_card_image_ep(card_id: str, db=Depends(get_db)):
    from db.models import CardImageOverride
    db.query(CardImageOverride).filter(
        CardImageOverride.card_id == card_id).delete()
    db.commit()
    IMAGE_OVERRIDES.pop(card_id, None)
    return {"card_id": card_id, "cleared": True}


@app.get("/api/cards/overrides")
def list_card_overrides_ep():
    return {"overrides": [{"card_id": k, "image": v} for k, v in IMAGE_OVERRIDES.items()]}


# --------------------------------------------------------------------------- #
# Authenticated: save + list game history; admin: list users
# --------------------------------------------------------------------------- #
@app.post("/api/game/{gid}/save")
def save_game(gid: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    sess = SESSIONS.get(gid)
    if not sess:
        raise HTTPException(404, "game not found")
    st = sess.engine.state
    winner_name = st.players[st.winner].name if st.winner is not None else None
    rec = GameRecord(
        user_id=user.id, mode=sess.mode,
        deck_a=st.players[0].name, deck_b=st.players[1].name,
        agent_a=str(type(sess.agents.get(0)).__name__ if sess.agents.get(0) else "human"),
        agent_b=str(type(sess.agents.get(1)).__name__ if sess.agents.get(1) else "human"),
        winner=winner_name, turns=st.turn_number, log="\n".join(st.log[-60:]),
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return {"saved": True, "record_id": rec.id}


@app.get("/api/me/games")
def my_games(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = (db.query(GameRecord)
            .filter(GameRecord.user_id == user.id)
            .order_by(GameRecord.created_at.desc()).limit(50).all())
    return {"games": [
        {"id": r.id, "mode": r.mode, "deck_a": r.deck_a, "deck_b": r.deck_b,
         "winner": r.winner, "turns": r.turns,
         "created_at": r.created_at.isoformat()} for r in rows
    ]}


@app.get("/api/admin/users")
def admin_users(user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not user.is_admin:
        raise HTTPException(403, "admin only")
    rows = db.query(User).order_by(User.created_at.asc()).all()
    return {"users": [
        {"id": u.id, "username": u.username, "email": u.email,
         "is_admin": u.is_admin, "created_at": u.created_at.isoformat()} for u in rows
    ]}
