"""Two-human multiplayer matches.

The server holds an authoritative `GameEngine` per match. Each player has a
secret seat token; state is masked per seat (you only see your own hand). Two
modes:

* **async** — correspondence: submit a move, the opponent is notified by
  polling; no clock.
* **timed** — each turn has a deadline; if it lapses the server auto-finishes
  that player's turn with the heuristic so play never stalls.

Every move is recorded as a behavioural-cloning sample (state encoding, the
features of each legal action, and the chosen index). When the game ends, the
*winner's* samples are handed to a callback so the agents can learn the
strategy that won (see `rl/imitation.py`).
"""
from __future__ import annotations

import secrets
import threading
import time
import uuid
from typing import Callable, Optional

from engine.actions import ActionType
from engine.game import GameEngine

MATCHES: dict[str, dict] = {}
_LOCK = threading.RLock()
_MAX_AUTO_STEPS = 80  # cap when auto-finishing a timed-out turn

# Optional durable backing store (set by the API at startup). When present,
# matches are written through to Postgres so they survive a restart; a match is
# reconstructed deterministically by replaying its recorded moves.
_STORE = None


def set_store(store) -> None:
    global _STORE
    _STORE = store


def _save(m: dict) -> None:
    if _STORE is not None:
        try:
            _STORE.save(m)
        except Exception:
            pass


def hydrate() -> None:
    """Load any in-progress matches from the store into memory on startup."""
    if _STORE is None:
        return
    try:
        for m in _STORE.load_open():
            MATCHES[m["id"]] = m
    except Exception:
        pass


def _label(eng: GameEngine, a) -> str:
    me = eng.state.current
    try:
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
    except Exception:
        pass
    return {ActionType.USE_ABILITY: "Use Ability", ActionType.RETREAT: "Retreat",
            ActionType.END_TURN: "End Turn"}.get(a.type, a.type.value)


def create_match(deck_a, deck_b, deck_a_id, deck_b_id, mode, turn_seconds, host_name) -> tuple[str, str]:
    mid = uuid.uuid4().hex[:10]
    seed = secrets.randbelow(2**31)
    eng = GameEngine.new_game(deck_a, deck_b,
                              names=(host_name or "Player 1", "Player 2"), seed=seed)
    token = secrets.token_hex(8)
    with _LOCK:
        MATCHES[mid] = {
            "id": mid, "engine": eng, "mode": mode,
            "turn_seconds": int(turn_seconds), "deck_ids": [deck_a_id, deck_b_id],
            "deck_cards": [deck_a, deck_b], "seed": seed, "moves": [],
            "seats": {0: {"token": token, "name": host_name or "Player 1", "joined": True},
                      1: {"token": None, "name": None, "joined": False}},
            "status": "waiting", "winner": None, "turn_player": None, "deadline": None,
            "created": time.time(), "last": time.time(),
            "join_code": mid[:6].upper(), "captured": 0,
        }
        _save(MATCHES[mid])
    return mid, token


def join_match(mid: str, name: str) -> tuple[Optional[str], Optional[str]]:
    with _LOCK:
        m = get_match(mid)
        if not m:
            return None, "match not found"
        if m["seats"][1]["joined"]:
            return None, "match is full"
        token = secrets.token_hex(8)
        m["seats"][1] = {"token": token, "name": name or "Player 2", "joined": True}
        try:
            m["engine"].state.players[1].name = name or "Player 2"
        except Exception:
            pass
        m["status"] = "active"
        _sync_turn(m)
        _save(m)
        return token, None


def seat_of(m: dict, token: Optional[str]) -> Optional[int]:
    if not token:
        return None
    for s, info in m["seats"].items():
        if info["token"] and info["token"] == token:
            return s
    return None


def _sync_turn(m: dict) -> None:
    eng = m["engine"]
    cp = None if eng.state.is_over() else eng.state.current_player
    if cp != m.get("turn_player"):
        m["turn_player"] = cp
        if m["mode"] == "timed" and m["status"] == "active" and cp is not None:
            m["deadline"] = time.time() + m["turn_seconds"]
        else:
            m["deadline"] = None


def _auto_finish_turn(m: dict) -> None:
    """Heuristic plays out the current (timed-out) player's turn so the match
    advances; each move is recorded so the game can be replayed/reconstructed."""
    from agents.basic_agents import HeuristicAgent
    eng = m["engine"]
    bot = HeuristicAgent()
    start = eng.state.current_player
    steps = 0
    while (not eng.state.is_over() and eng.state.current_player == start
           and steps < _MAX_AUTO_STEPS):
        legal = eng.legal_actions()
        if not legal:
            break
        a = bot.select(eng)
        try:
            idx = legal.index(a)
        except ValueError:
            idx = 0
            a = legal[0]
        m["moves"].append(idx)
        eng.apply(a)
        steps += 1
    m["last"] = time.time()


def enforce_timeout(m: dict, on_finalize: Optional[Callable[[dict], None]] = None) -> None:
    if m["mode"] != "timed" or m["status"] != "active":
        return
    if m["deadline"] and time.time() > m["deadline"] and not m["engine"].state.is_over():
        _auto_finish_turn(m)
        if m["engine"].state.is_over():
            _finalize(m, on_finalize)
        else:
            _sync_turn(m)
        _save(m)


def _finalize(m: dict, on_finalize: Optional[Callable[[dict], None]]) -> None:
    if m["status"] == "over":
        return
    m["status"] = "over"
    m["winner"] = m["engine"].state.winner
    m["deadline"] = None
    if on_finalize:
        try:
            on_finalize(m)
        except Exception:
            pass
    _save(m)


def apply_index(mid: str, token: str, index: int,
                on_finalize: Optional[Callable[[dict], None]] = None) -> tuple[Optional[dict], Optional[str]]:
    with _LOCK:
        m = get_match(mid)
        if not m:
            return None, "match not found"
        seat = seat_of(m, token)
        if seat is None:
            return None, "invalid token"
        enforce_timeout(m, on_finalize)
        eng = m["engine"]
        if m["status"] != "active" or eng.state.is_over():
            return public_state(m, token), None
        if eng.state.current_player != seat:
            return None, "not your turn"
        legal = eng.legal_actions()
        if index < 0 or index >= len(legal):
            return None, "illegal action index"
        m["moves"].append(index)
        eng.apply(legal[index])
        m["last"] = time.time()
        if eng.state.is_over():
            _finalize(m, on_finalize)
        else:
            _sync_turn(m)
            _save(m)
        return public_state(m, token), None


def winner_samples(m: dict) -> list[dict]:
    """Reconstruct the winner's decisions as behavioural-cloning samples by
    replaying the recorded moves (works even after a restart, since only the
    move sequence is persisted)."""
    w = m["winner"]
    if w is None:
        return []
    try:
        from rl import encoder
        da, db = m["deck_cards"]
        eng = GameEngine.new_game(da, db, seed=m["seed"])
    except Exception:
        return []
    out: list[dict] = []
    for idx in m["moves"]:
        if eng.state.is_over():
            break
        legal = eng.legal_actions()
        if idx < 0 or idx >= len(legal):
            break
        if eng.state.current_player == w:
            out.append({
                "state": encoder.encode_state(eng, w).tolist(),
                "action_feats": encoder.encode_actions(eng, legal).tolist(),
                "chosen_index": idx,
            })
        eng.apply(legal[idx])
    return out


def public_state(m: dict, token: Optional[str] = None,
                 on_finalize: Optional[Callable[[dict], None]] = None) -> dict:
    enforce_timeout(m, on_finalize)
    eng = m["engine"]
    seat = seat_of(m, token)
    over = eng.state.is_over()
    your_turn = (not over and m["status"] == "active"
                 and seat is not None and eng.state.current_player == seat)
    legal = []
    if your_turn:
        for i, a in enumerate(eng.legal_actions()):
            legal.append({"index": i, "type": a.type.value, "label": _label(eng, a)})
    time_left = None
    if m["mode"] == "timed" and m["deadline"] and not over and m["status"] == "active":
        time_left = max(0.0, round(m["deadline"] - time.time(), 1))
    return {
        "match_id": m["id"], "status": m["status"], "mode": m["mode"],
        "turn_seconds": m["turn_seconds"], "join_code": m["join_code"],
        "your_seat": seat, "over": over, "winner": m["winner"],
        "current_player": None if over else eng.state.current_player,
        "your_turn": your_turn, "legal": legal, "time_left": time_left,
        "deck_ids": m["deck_ids"],
        "seats": {str(s): {"name": info["name"], "joined": info["joined"]}
                  for s, info in m["seats"].items()},
        "state": eng.state.to_dict(viewer=seat),
        "winner_samples": (len(winner_samples(m)) if over else None),
    }


def get_match(mid: str) -> Optional[dict]:
    m = MATCHES.get(mid)
    if m is None and _STORE is not None:
        try:
            m = _STORE.load(mid)
        except Exception:
            m = None
        if m is not None:
            MATCHES[mid] = m
    return m


def open_matches() -> list[dict]:
    with _LOCK:
        seen: set[str] = set()
        out: list[dict] = []
        for m in MATCHES.values():
            if m["status"] == "waiting":
                out.append({"match_id": m["id"], "join_code": m["join_code"],
                            "host": m["seats"][0]["name"], "mode": m["mode"],
                            "turn_seconds": m["turn_seconds"], "decks": m["deck_ids"]})
                seen.add(m["id"])
        if _STORE is not None:                  # durable: include matches not yet hydrated
            try:
                for meta in _STORE.list_open_meta():
                    if meta["match_id"] not in seen:
                        out.append(meta)
                        seen.add(meta["match_id"])
            except Exception:
                pass
        return out
