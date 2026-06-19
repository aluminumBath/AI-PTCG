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
    try:
        from multiplayer import match_store, service as mp_service
        match_store.init(_resolve_deck)         # resolves builtin + imported decks
        mp_service.set_store(match_store)        # write matches through to Postgres
        mp_service.hydrate()                     # reload in-progress matches after a restart
    except Exception as exc:
        print(f"[startup] multiplayer store skipped: {exc}")


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
    from data.deck_select import resolve_deck_token
    seed = req.seed if req.seed is not None else random.randint(0, 2**31 - 1)

    # Which agent (if any) sits in each seat — used for "agent's pick" decks.
    if req.mode == "human_vs_ai":
        ai_seat = 1 - req.human_seat
        seat_agent = {req.human_seat: None, ai_seat: req.agent_b}
    else:
        seat_agent = {0: req.agent_a, 1: req.agent_b}

    # 'random' / 'auto' resolve to a concrete deck id (seat B avoids mirroring A).
    deck_a_id = resolve_deck_token(req.deck_a, seat_agent.get(0), seed + 101)
    deck_b_id = resolve_deck_token(req.deck_b, seat_agent.get(1), seed + 202, exclude=deck_a_id)

    deck_a_cards = _resolve_deck(deck_a_id)
    deck_b_cards = _resolve_deck(deck_b_id)
    engine = GameEngine.new_game(
        deck_a_cards, deck_b_cards,
        names=(deck_a_id, deck_b_id), seed=seed,
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
    return {"game_id": gid, "seed": seed,
            "deck_a": deck_a_id, "deck_b": deck_b_id,
            "state": _view(SESSIONS[gid])}


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
        "result": None, "error": None, "current": None,
        "config": {"agents": agent_ids, "decks": req.decks, "games_per_pairing": games},
    }

    def worker():
        try:
            def prog(d, t):
                TOURNAMENTS[job_id]["done"] = d
                TOURNAMENTS[job_id]["total"] = t

            def on_state(snap):
                TOURNAMENTS[job_id]["current"] = snap

            res = run_tournament(
                agent_ids, req.decks, games,
                deck_resolver=_resolve_deck, checkpoint=CKPT, progress=prog,
                should_continue=lambda: not TOURNAMENTS[job_id].get("cancel"),
                on_state=on_state,
            )
            TOURNAMENTS[job_id]["result"] = res
            TOURNAMENTS[job_id]["current"] = None  # tournament finished; drop live frame
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


@app.get("/api/tournament/{job_id}/validate")
def tournament_validate(job_id: str):
    """Attach confidence intervals + sanity checks to a finished tournament."""
    job = TOURNAMENTS.get(job_id)
    if not job:
        raise HTTPException(404, "tournament not found")
    if not job.get("result"):
        raise HTTPException(400, "tournament has no result yet")
    from eval.validate import validate_tournament
    return validate_tournament(job["result"])


# --- Consistency: repeated seeded batches -> mean ± standard deviation ------ #
CONSISTENCY: dict[str, dict] = {}


class ConsistencyReq(BaseModel):
    agent_a: str
    agent_b: str = "random"
    decks: list[str] = ["charizard_ex", "gardevoir_ex"]
    batches: int = 5
    games_per_batch: int = 20
    seed: Optional[int] = None


@app.post("/api/validate/consistency")
def consistency_run(req: ConsistencyReq):
    import random as _r
    from eval.validate import run_consistency
    batches = max(2, min(20, req.batches))
    gpb = max(2, min(50, req.games_per_batch))
    decks = req.decks or ["charizard_ex", "gardevoir_ex"]
    seed = req.seed if req.seed is not None else _r.randint(0, 2**31 - 1)
    job_id = uuid.uuid4().hex[:12]
    CONSISTENCY[job_id] = {
        "status": "running", "done": 0, "total": batches * gpb, "cancel": False,
        "result": None, "error": None,
        "config": {"agent_a": req.agent_a, "agent_b": req.agent_b,
                   "batches": batches, "games_per_batch": gpb, "decks": decks},
    }

    def worker():
        try:
            def prog(d, t):
                CONSISTENCY[job_id]["done"] = d
                CONSISTENCY[job_id]["total"] = t
            res = run_consistency(
                req.agent_a, req.agent_b, decks, batches, gpb,
                deck_resolver=_resolve_deck, checkpoint=CKPT, seed=seed,
                progress=prog,
                should_continue=lambda: not CONSISTENCY[job_id].get("cancel"),
            )
            CONSISTENCY[job_id]["result"] = res
            CONSISTENCY[job_id]["status"] = "cancelled" if res.get("cancelled") else "done"
        except Exception as exc:
            CONSISTENCY[job_id]["status"] = "error"
            CONSISTENCY[job_id]["error"] = str(exc)

    threading.Thread(target=worker, daemon=True).start()
    return {"job_id": job_id, "total_games": batches * gpb}


@app.get("/api/validate/consistency/{job_id}")
def consistency_status(job_id: str):
    job = CONSISTENCY.get(job_id)
    if not job:
        raise HTTPException(404, "consistency job not found")
    return job


@app.post("/api/validate/consistency/{job_id}/cancel")
def consistency_cancel(job_id: str):
    job = CONSISTENCY.get(job_id)
    if not job:
        raise HTTPException(404, "consistency job not found")
    if job["status"] == "running":
        job["cancel"] = True
    return {"job_id": job_id, "status": job["status"], "cancelling": job.get("cancel", False)}


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


def _agent_label(agent_id: str) -> str:
    from agents.registry import list_agents
    for a in list_agents():
        if a.get("id") == agent_id:
            return a.get("label", agent_id)
    return agent_id


@app.get("/api/competition/export/sim")
def competition_export_sim(deck: str, agent: str = "ismcts"):
    """Build a Simulation submission as submission.tar.gz (top-level main.py +
    deck.csv + README). Add the cg/ library and re-tar to submit."""
    from fastapi.responses import Response
    from competition.export import build_sim_bundle
    try:
        _resolve_deck(deck)  # validate the deck id (raises if unknown)
    except Exception:
        raise HTTPException(404, f"unknown deck '{deck}'")
    blob = build_sim_bundle(deck, agent, _agent_label(agent), _resolve_deck)
    return Response(
        content=blob, media_type="application/gzip",
        headers={"Content-Disposition": 'attachment; filename="submission.tar.gz"'},
    )


@app.get("/api/competition/export/strategy")
def competition_export_strategy(deck: str, agent: str = "ismcts",
                                title: str = "", subtitle: str = ""):
    """Build a Strategy-category Writeup (Markdown, <= 2000 words) for the deck +
    agent, structured around the Model/Deck/Report rubric."""
    from fastapi.responses import Response
    from competition.export import build_strategy_writeup
    try:
        _resolve_deck(deck)
    except Exception:
        raise HTTPException(404, f"unknown deck '{deck}'")
    # fold in the latest stats for this model if we have them
    stats = None
    try:
        from stats.model_stats import list_stats
        for row in list_stats():
            if row.get("model") == agent and row.get("games"):
                stats = {"games": row["games"], "winrate": row.get("winrate", 0)}
                break
    except Exception:
        stats = None
    md = build_strategy_writeup(deck, agent, _agent_label(agent),
                                title=title or None, subtitle=subtitle or None,
                                stats=stats)
    return Response(
        content=md, media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="writeup.md"'},
    )


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
# Two-human multiplayer + learning the winner's strategy
# --------------------------------------------------------------------------- #
from multiplayer import service as mp_service  # noqa: E402

HUMAN_DATASET = os.path.join(_BACKEND_ROOT, "data_store", "human_games.jsonl")
LEARN_JOBS: dict[str, dict] = {}


def _capture_winner(m: dict) -> None:
    """on_finalize hook: persist the winner's moves as imitation samples + a row."""
    import json
    samples = mp_service.winner_samples(m)
    if samples:
        try:
            os.makedirs(os.path.dirname(HUMAN_DATASET), exist_ok=True)
            with open(HUMAN_DATASET, "a", encoding="utf-8") as fh:
                for s in samples:
                    fh.write(json.dumps(s) + "\n")
        except Exception:
            pass
    try:
        from db.database import SessionLocal
        from db.models import HumanGame
        db = SessionLocal()
        try:
            w = m["winner"]
            db.add(HumanGame(
                match_id=m["id"], mode=m["mode"],
                deck_a=m["deck_ids"][0], deck_b=m["deck_ids"][1],
                winner_seat=(w if w is not None else -1),
                winner_name=(m["seats"][w]["name"] if w is not None else "draw"),
                turns=m["engine"].state.turn_number, samples=len(samples),
            ))
            db.commit()
        finally:
            db.close()
    except Exception:
        pass


class MPCreateReq(BaseModel):
    deck_a: str = "charizard_ex"
    deck_b: str = "gardevoir_ex"
    mode: str = "async"            # 'async' | 'timed'
    turn_seconds: int = 90
    name: str = "Player 1"


class MPJoinReq(BaseModel):
    name: str = "Player 2"


class MPActionReq(BaseModel):
    index: int


@app.post("/api/multiplayer/create")
def mp_create(req: MPCreateReq):
    da, db_ = _resolve_deck(req.deck_a), _resolve_deck(req.deck_b)
    mode = req.mode if req.mode in ("async", "timed") else "async"
    secs = max(15, min(600, req.turn_seconds))
    mid, token = mp_service.create_match(da, db_, req.deck_a, req.deck_b, mode, secs, req.name)
    return {"match_id": mid, "token": token, "seat": 0,
            "join_code": mp_service.get_match(mid)["join_code"]}


@app.post("/api/multiplayer/{mid}/join")
def mp_join(mid: str, req: MPJoinReq):
    token, err = mp_service.join_match(mid, req.name)
    if err:
        raise HTTPException(404 if "not found" in err else 409, err)
    return {"match_id": mid, "token": token, "seat": 1}


@app.get("/api/multiplayer/open")
def mp_open():
    return {"matches": mp_service.open_matches()}


@app.get("/api/multiplayer/{mid}/state")
def mp_state(mid: str, token: str = ""):
    m = mp_service.get_match(mid)
    if not m:
        raise HTTPException(404, "match not found")
    return mp_service.public_state(m, token or None, on_finalize=_capture_winner)


@app.post("/api/multiplayer/{mid}/action")
def mp_action(mid: str, req: MPActionReq, token: str = ""):
    view, err = mp_service.apply_index(mid, token, req.index, on_finalize=_capture_winner)
    if err:
        code = 404 if "not found" in err else (403 if "token" in err or "your turn" in err else 400)
        raise HTTPException(code, err)
    return view


@app.post("/api/multiplayer/{mid}/rematch")
def mp_rematch(mid: str, token: str = "", swap: bool = False):
    """Start a fresh match with the same decks, mode, and clock as a finished
    (or in-progress) one. The requester becomes the host (seat 0); the new match
    appears in the lobby for the opponent to join."""
    m = mp_service.get_match(mid)
    if not m:
        raise HTTPException(404, "match not found")
    seat = mp_service.seat_of(m, token)
    if seat is None:
        raise HTTPException(403, "invalid token")
    da_id, db_id = m["deck_ids"]
    if swap:
        da_id, db_id = db_id, da_id
    host_name = m["seats"][seat]["name"] or "Player 1"
    new_mid, new_token = mp_service.create_match(
        _resolve_deck(da_id), _resolve_deck(db_id), da_id, db_id,
        m["mode"], m["turn_seconds"], host_name)
    nm = mp_service.get_match(new_mid)
    return {"match_id": new_mid, "token": new_token, "seat": 0,
            "join_code": nm["join_code"], "from_match": mid}


@app.get("/api/multiplayer/learned")
def mp_learned():
    """Captured human games + a peek at what winning humans tended to do."""
    import json
    from collections import Counter
    from engine.actions import ActionType
    from db.database import SessionLocal
    from db.models import HumanGame
    db = SessionLocal()
    try:
        rows = db.query(HumanGame).order_by(HumanGame.created_at.desc()).all()
        games = [{"match_id": r.match_id, "mode": r.mode, "deck_a": r.deck_a,
                  "deck_b": r.deck_b, "winner_seat": r.winner_seat,
                  "winner_name": r.winner_name, "turns": r.turns,
                  "samples": r.samples, "created_at": r.created_at.isoformat()}
                 for r in rows]
    finally:
        db.close()
    # action-type tendencies of winners, decoded from the dataset's chosen actions
    atypes = list(ActionType)
    mix = Counter()
    total_samples = 0
    if os.path.exists(HUMAN_DATASET):
        try:
            with open(HUMAN_DATASET, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    total_samples += 1
                    d = json.loads(line)
                    feats = d.get("action_feats") or []
                    idx = d.get("chosen_index", -1)
                    if 0 <= idx < len(feats):
                        onehot = feats[idx][8:8 + len(atypes)]
                        if onehot:
                            mix[atypes[int(max(range(len(onehot)), key=lambda i: onehot[i]))].value] += 1
        except Exception:
            pass
    return {"games": games, "total_games": len(games), "total_samples": total_samples,
            "winner_action_mix": dict(mix.most_common()),
            "can_learn": total_samples >= 10}


@app.get("/api/multiplayer/dataset")
def mp_dataset():
    from fastapi.responses import FileResponse
    if not os.path.exists(HUMAN_DATASET):
        raise HTTPException(404, "no human games captured yet")
    return FileResponse(HUMAN_DATASET, media_type="application/x-ndjson",
                        filename="human_games.jsonl")


class LearnReq(BaseModel):
    epochs: int = 6
    lr: float = 1e-3


@app.post("/api/multiplayer/learn")
def mp_learn(req: LearnReq):
    """Behaviourally-clone the captured human-winner moves into the policy the
    `rl`/`rl_mcts` agents use, as a background job."""
    import threading
    job_id = uuid.uuid4().hex[:12]
    LEARN_JOBS[job_id] = {"status": "running", "history": [], "samples": 0, "error": None}

    def worker():
        try:
            from rl.imitation import clone_from_file
            res = clone_from_file(
                HUMAN_DATASET, CKPT, CKPT,
                epochs=max(1, min(50, req.epochs)), lr=req.lr, min_samples=10,
                log=lambda rec: LEARN_JOBS[job_id]["history"].append(rec),
            )
            LEARN_JOBS[job_id].update(status="done", samples=res["samples"])
        except Exception as exc:
            LEARN_JOBS[job_id].update(status="error", error=str(exc))

    threading.Thread(target=worker, daemon=True).start()
    return {"job_id": job_id}


@app.get("/api/multiplayer/learn/{job_id}")
def mp_learn_status(job_id: str):
    job = LEARN_JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "learn job not found")
    return job


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


# --------------------------------------------------------------------------- #
# Favorites — a user's saved decks / cards / sets, surfaced for quick battle
# --------------------------------------------------------------------------- #
_FAV_KINDS = {"deck", "card", "set"}


class FavReq(BaseModel):
    kind: str
    ref_id: str


def _valid_favorite(kind: str, ref_id: str) -> bool:
    if not ref_id or len(ref_id) > 64:
        return False
    if kind == "set":
        from data.cards_db import builtin_sets
        return any(s["code"] == ref_id for s in builtin_sets())
    if kind == "deck":
        try:
            _resolve_deck(ref_id)   # builtin or imported deck
            return True
        except Exception:
            return False
    if kind == "card":
        return True  # card ids come from the live catalogue; accept any well-formed id
    return False


def _favorites_for(user, db) -> dict:
    from db.models import Favorite
    rows = (db.query(Favorite).filter(Favorite.user_id == user.id)
            .order_by(Favorite.created_at.asc()).all())
    out = {"deck": [], "card": [], "set": []}
    for r in rows:
        out.setdefault(r.kind, []).append(r.ref_id)
    return {"decks": out["deck"], "cards": out["card"], "sets": out["set"]}


@app.get("/api/favorites")
def favorites_list(user: User = Depends(current_user), db=Depends(get_db)):
    return _favorites_for(user, db)


@app.post("/api/favorites")
def favorites_add(req: FavReq, user: User = Depends(current_user), db=Depends(get_db)):
    from db.models import Favorite
    if req.kind not in _FAV_KINDS:
        raise HTTPException(400, "kind must be one of: deck, card, set")
    if not _valid_favorite(req.kind, req.ref_id):
        raise HTTPException(404, f"unknown {req.kind} '{req.ref_id}'")
    exists = (db.query(Favorite)
              .filter_by(user_id=user.id, kind=req.kind, ref_id=req.ref_id).first())
    if not exists:
        db.add(Favorite(user_id=user.id, kind=req.kind, ref_id=req.ref_id))
        db.commit()
    return _favorites_for(user, db)


@app.delete("/api/favorites/{kind}/{ref_id}")
def favorites_remove(kind: str, ref_id: str,
                     user: User = Depends(current_user), db=Depends(get_db)):
    from db.models import Favorite
    (db.query(Favorite)
     .filter_by(user_id=user.id, kind=kind, ref_id=ref_id).delete())
    db.commit()
    return _favorites_for(user, db)
