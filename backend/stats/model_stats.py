"""Lifetime model scoreboard.

Records the outcome of *every* game that involves an agent/model — AI-vs-AI
spectator games, Play-vs-AI, Model Arena tournaments, and ladder episodes — into
a persistent per-model aggregate (wins / losses / draws). The scoreboard powers
the Scores tab and the JSON/CSV export.

``record_game`` opens its own session per call so it is safe to invoke from the
request handlers and from background threads (tournament / ladder) alike.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.exc import IntegrityError

from db.database import SessionLocal
from db.models import ModelStat

_OPP = {"win": "loss", "loss": "win", "draw": "draw"}


def _bump(db, model_id: str, outcome: str) -> None:
    if not model_id:
        return
    row = db.query(ModelStat).filter(ModelStat.model_id == model_id).one_or_none()
    if row is None:
        row = ModelStat(model_id=model_id, games=0, wins=0, losses=0, draws=0)
        db.add(row)
        try:
            db.flush()
        except IntegrityError:           # created concurrently — fetch it
            db.rollback()
            row = db.query(ModelStat).filter(ModelStat.model_id == model_id).one()
    row.games += 1
    if outcome == "win":
        row.wins += 1
    elif outcome == "loss":
        row.losses += 1
    else:
        row.draws += 1
    row.updated_at = datetime.utcnow()


def record_single(model_id: str, outcome: str) -> None:
    """Record one result for a single model (e.g. the AI seat in Play-vs-AI)."""
    db = SessionLocal()
    try:
        _bump(db, model_id, outcome)
        db.commit()
    finally:
        db.close()


def record_game(model_a: str, model_b: str, result: str) -> None:
    """Record a game between two models. ``result`` is 'a', 'b', or 'draw'/None."""
    outcome_a = "win" if result == "a" else "loss" if result == "b" else "draw"
    db = SessionLocal()
    try:
        _bump(db, model_a, outcome_a)
        _bump(db, model_b, _OPP[outcome_a])
        db.commit()
    finally:
        db.close()


def _row_dict(r: ModelStat, label_of) -> dict:
    points = r.wins + 0.5 * r.draws
    return {
        "model_id": r.model_id,
        "label": label_of(r.model_id),
        "games": r.games,
        "wins": r.wins,
        "losses": r.losses,
        "draws": r.draws,
        "win_rate": round(r.wins / r.games, 3) if r.games else 0.0,
        "points": round(points, 1),
        "points_per_game": round(points / r.games, 3) if r.games else 0.0,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


def list_stats() -> list[dict]:
    from agents.registry import REGISTRY
    label_of = lambda m: REGISTRY.get(m, {}).get("label", m)
    db = SessionLocal()
    try:
        rows = db.query(ModelStat).all()
        out = [_row_dict(r, label_of) for r in rows]
        out.sort(key=lambda d: (d["win_rate"], d["games"]), reverse=True)
        return out
    finally:
        db.close()


def reset_stats() -> int:
    db = SessionLocal()
    try:
        n = db.query(ModelStat).delete()
        db.commit()
        return n
    finally:
        db.close()


def export_csv() -> str:
    rows = list_stats()
    head = "model_id,label,games,wins,losses,draws,win_rate,points,points_per_game"
    lines = [head] + [
        f'{r["model_id"]},"{r["label"]}",{r["games"]},{r["wins"]},{r["losses"]},'
        f'{r["draws"]},{r["win_rate"]},{r["points"]},{r["points_per_game"]}'
        for r in rows
    ]
    return "\n".join(lines) + "\n"
