"""Deck selection for the game setup.

Lets a side's deck be a concrete id, **random**, or the **agent's pick** — a
deck chosen to match the agent's playstyle. The style-aware agents (aggro /
control / setup) draw from a matching pool; every other model (heuristic,
greedy, search, learned, ensembles) has no fixed style and draws from a
versatile midrange/combo pool.
"""
from __future__ import annotations

import random
from typing import Optional

from data.cards_db import DECK_META

# Agents whose identity implies a deck style. Anything not listed is "balanced".
_AGENT_STYLE = {
    "aggro": "aggro",
    "control": "control",
    "setup": "setup",
}

_STYLES = ("aggro", "control", "setup")


def _style_of_archetype(archetype: str) -> str:
    a = (archetype or "").lower()
    if "aggro" in a or "tempo" in a:
        return "aggro"
    if any(k in a for k in ("control", "status", "disruption", "paralysis",
                            "burn", "tanky", "healing", "lock")):
        return "control"
    return "setup"  # midrange / combo / scaling / bench-spread / toolbox


def decks_by_style() -> dict[str, list[str]]:
    out: dict[str, list[str]] = {s: [] for s in _STYLES}
    for deck_id, meta in DECK_META.items():
        out[_style_of_archetype(meta.get("archetype", ""))].append(deck_id)
    return out


def all_deck_ids() -> list[str]:
    return list(DECK_META.keys())


def agent_style(agent_id: Optional[str]) -> Optional[str]:
    return _AGENT_STYLE.get(agent_id or "")


def pick_deck(agent_id: Optional[str], mode: str, seed: int = 0,
              exclude: Optional[str] = None) -> str:
    """Return a deck id.

    mode='random' -> any legal deck.
    mode='agent'  -> a deck matching the agent's style; style-less agents get a
                     versatile (midrange/combo) deck. Falls back to any deck.
    Seeded for reproducibility; ``exclude`` avoids mirroring the opponent when
    other options exist.
    """
    rng = random.Random(seed)
    pool = all_deck_ids()

    if mode == "agent":
        by_style = decks_by_style()
        style = agent_style(agent_id) or "setup"  # balanced default
        styled = by_style.get(style, [])
        if styled:
            pool = styled

    if exclude and len(pool) > 1:
        alt = [d for d in pool if d != exclude]
        if alt:
            pool = alt

    if not pool:                       # absolute fallback
        pool = all_deck_ids()
    return rng.choice(pool)


# Sentinel deck tokens accepted by the API in place of a deck id.
_RANDOM_TOKENS = {"random", "__random__"}
_AGENT_TOKENS = {"auto", "agent", "agents pick", "agent's pick", "__agent__"}


def resolve_deck_token(token: Optional[str], agent_id: Optional[str],
                       seed: int, exclude: Optional[str] = None) -> str:
    """Map a deck field that may be a sentinel ('random' / 'auto') to a concrete
    deck id; a normal deck id is returned unchanged."""
    t = (token or "").strip().lower()
    if t in _RANDOM_TOKENS:
        return pick_deck(agent_id, "random", seed, exclude)
    if t in _AGENT_TOKENS:
        return pick_deck(agent_id, "agent", seed, exclude)
    return token
