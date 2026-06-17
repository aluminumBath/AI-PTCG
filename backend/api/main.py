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
from db.database import get_db, init_db
from db.models import User, GameRecord
from db.seed import seed_admin
from auth.routes import router as auth_router, current_user

app = FastAPI(title="Pokémon TCG AI Arena", version="1.0")
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

_BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CKPT = os.environ.get(
    "RL_CHECKPOINT",
    os.path.join(_BACKEND_ROOT, "checkpoints", "policy_latest.pt"),
)


def _make_agent(kind: str):
    from agents.basic_agents import RandomAgent, HeuristicAgent
    if kind == "random":
        return RandomAgent()
    if kind == "heuristic":
        return HeuristicAgent()
    if kind == "mcts":
        from agents.mcts_agent import MCTSAgent
        return MCTSAgent(iterations=120)
    if kind == "rl":
        try:
            from rl.agent import RLAgent
            return RLAgent(CKPT, temperature=0.0)
        except Exception:
            return HeuristicAgent()
    return HeuristicAgent()


class Session:
    def __init__(self, engine: GameEngine, mode: str, agents: dict, human_seat: Optional[int]):
        self.engine = engine
        self.mode = mode
        self.agents = agents          # seat -> agent (for AI seats)
        self.human_seat = human_seat


SESSIONS: dict[str, Session] = {}


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
    return {"decks": list(DECKS.keys())}


@app.get("/api/agents")
def agents():
    return {"agents": ["random", "heuristic", "mcts", "rl"]}


@app.post("/api/game/new")
def new_game(req: NewGame):
    if req.deck_a not in DECKS or req.deck_b not in DECKS:
        raise HTTPException(400, "unknown deck")
    import random
    seed = req.seed if req.seed is not None else random.randint(0, 2**31 - 1)
    engine = GameEngine.new_game(
        DECKS[req.deck_a](), DECKS[req.deck_b](),
        names=(req.deck_a, req.deck_b), seed=seed,
    )
    if req.mode == "human_vs_ai":
        ai_seat = 1 - req.human_seat
        agents = {ai_seat: _make_agent(req.agent_b)}
        human_seat = req.human_seat
    else:
        agents = {0: _make_agent(req.agent_a), 1: _make_agent(req.agent_b)}
        human_seat = None
    gid = uuid.uuid4().hex[:12]
    SESSIONS[gid] = Session(engine, req.mode, agents, human_seat)
    return {"game_id": gid, "seed": seed, "state": _view(SESSIONS[gid])}


def _view(sess: Session) -> dict:
    viewer = sess.human_seat  # None -> full view for spectating
    state = sess.engine.state.to_dict(viewer=viewer)
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
    guard = 0
    while (not eng.state.is_over()
           and eng.state.current_player != sess.human_seat
           and guard < 500):
        ai = sess.agents.get(eng.state.current_player)
        eng.apply(ai.select(eng))
        guard += 1
    return {"done": eng.state.is_over(), "state": _view(sess)}


@app.get("/api/training/metrics")
def training_metrics():
    import json
    path = os.path.join(_BACKEND_ROOT, "checkpoints", "metrics.json")
    if not os.path.exists(path):
        return {"metrics": [], "note": "No training run yet. Run python -m rl.train"}
    with open(path) as fh:
        return {"metrics": json.load(fh)}


@app.get("/api/cards/search")
def cards_search(q: str = "", page: int = 1, standard: bool = True):
    return card_api.search_cards(q, page=page, standard_only=standard)


@app.get("/api/cards/sets")
def cards_sets():
    return card_api.list_standard_sets()


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
