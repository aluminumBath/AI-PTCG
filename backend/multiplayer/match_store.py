"""Postgres-durable backing for multiplayer matches.

A live `GameEngine` isn't serialised directly; instead each match persists the
seed, the two deck ids, and the sequence of action indices played. Because the
engine is deterministic, replaying those moves from a fresh `new_game(seed)`
reconstructs the exact state — so matches survive a server restart.
"""
from __future__ import annotations

import json
import time
from typing import Callable, Optional

from engine.game import GameEngine

_resolver: Optional[Callable[[str], list]] = None


def init(deck_resolver: Callable[[str], list]) -> None:
    """Register how deck ids resolve to card lists (injected by the API so that
    imported/custom decks resolve too)."""
    global _resolver
    _resolver = deck_resolver


def _rebuild_engine(deck_a_id: str, deck_b_id: str, seed: int, moves: list[int]):
    da, db = _resolver(deck_a_id), _resolver(deck_b_id)
    eng = GameEngine.new_game(da, db, seed=seed)
    for idx in moves:
        if eng.state.is_over():
            break
        legal = eng.legal_actions()
        if 0 <= idx < len(legal):
            eng.apply(legal[idx])
        else:
            break
    return eng, da, db


def _row_to_match(row) -> dict:
    moves = json.loads(row.moves or "[]")
    eng, da, db = _rebuild_engine(row.deck_a, row.deck_b, row.seed, moves)
    over = eng.state.is_over()
    winner = None
    if row.status == "over":
        winner = None if (row.winner is None or row.winner < 0) else row.winner
    m = {
        "id": row.match_id, "engine": eng, "mode": row.mode,
        "turn_seconds": row.turn_seconds, "deck_ids": [row.deck_a, row.deck_b],
        "deck_cards": [da, db], "seed": row.seed, "moves": moves,
        "seats": {
            0: {"token": row.seat0_token, "name": row.seat0_name, "joined": row.seat0_joined},
            1: {"token": row.seat1_token, "name": row.seat1_name, "joined": row.seat1_joined},
        },
        "status": row.status, "winner": winner,
        "turn_player": (None if over else eng.state.current_player),
        "deadline": None,
        "created": row.created_at.timestamp() if row.created_at else time.time(),
        "last": time.time(), "join_code": row.join_code, "captured": row.captured or 0,
    }
    # give a fresh clock on reload so a restart doesn't instantly time a turn out
    if m["mode"] == "timed" and m["status"] == "active" and not over:
        m["deadline"] = time.time() + m["turn_seconds"]
    return m


def save(m: dict) -> None:
    from db.database import SessionLocal
    from db.models import MatchRecord
    db = SessionLocal()
    try:
        row = db.query(MatchRecord).filter_by(match_id=m["id"]).first()
        if not row:
            row = MatchRecord(match_id=m["id"])
            db.add(row)
        row.mode = m["mode"]
        row.turn_seconds = m["turn_seconds"]
        row.deck_a, row.deck_b = m["deck_ids"][0], m["deck_ids"][1]
        row.seed = m["seed"]
        row.moves = json.dumps(m["moves"])
        row.status = m["status"]
        if m["status"] == "over":
            row.winner = -1 if m["winner"] is None else m["winner"]
        else:
            row.winner = None
        row.seat0_token = m["seats"][0]["token"]
        row.seat0_name = m["seats"][0]["name"]
        row.seat0_joined = m["seats"][0]["joined"]
        row.seat1_token = m["seats"][1]["token"]
        row.seat1_name = m["seats"][1]["name"]
        row.seat1_joined = m["seats"][1]["joined"]
        row.join_code = m["join_code"]
        row.captured = m.get("captured", 0)
        db.commit()
    finally:
        db.close()


def load(match_id: str) -> Optional[dict]:
    from db.database import SessionLocal
    from db.models import MatchRecord
    db = SessionLocal()
    try:
        row = db.query(MatchRecord).filter_by(match_id=match_id).first()
        return _row_to_match(row) if row else None
    finally:
        db.close()


def load_open() -> list[dict]:
    """In-progress matches (waiting or active) to hydrate into memory on boot."""
    from db.database import SessionLocal
    from db.models import MatchRecord
    db = SessionLocal()
    try:
        rows = (db.query(MatchRecord)
                .filter(MatchRecord.status.in_(["waiting", "active"])).all())
        out = []
        for r in rows:
            try:
                out.append(_row_to_match(r))
            except Exception:
                pass  # a deck that no longer resolves, etc. — skip it
        return out
    finally:
        db.close()


def list_open_meta() -> list[dict]:
    """Lightweight lobby listing of joinable (waiting) matches — metadata only,
    no engine reconstruction."""
    from db.database import SessionLocal
    from db.models import MatchRecord
    db = SessionLocal()
    try:
        rows = db.query(MatchRecord).filter(MatchRecord.status == "waiting").all()
        return [{"match_id": r.match_id, "join_code": r.join_code, "host": r.seat0_name,
                 "mode": r.mode, "turn_seconds": r.turn_seconds,
                 "decks": [r.deck_a, r.deck_b]} for r in rows]
    finally:
        db.close()
