"""The Mind-reader — infer the opponent's deck, then counter it.

The competition's defining challenge is hidden information and adapting to an
opponent. This agent keeps a live **posterior over which of the 26 archetypes**
the opponent is playing, updated purely from *public* observations (their in-play
Pokémon and evolution chains, and both discard piles). It then classifies the
most-likely archetype's style and switches to the matchup-favoured counter-plan:

    opponent aggro   → play Control (out-sustain the race)
    opponent control → play Aggro   (race before they stabilise)
    opponent setup   → play Aggro   (pressure before the combo assembles)

When the read is still ambiguous it plays a balanced line. The chosen plan is run
through the Closer, so it never misses a lethal.

Faithfulness note: the simulator itself knows both decks, but this agent
deliberately restricts itself to information a player could actually see, to
demonstrate genuine opponent inference rather than peeking.
"""
from __future__ import annotations

import math
import random
from typing import Optional

from engine.actions import Action
from engine.game import GameEngine
from .basic_agents import Agent, HeuristicAgent
from .closer_agent import ClosingAgent
from .heuristic_strategies import make_strategy_agent

# counter-plan for an inferred opponent style
_COUNTER = {"aggro": "control", "control": "aggro", "setup": "aggro"}

_DECK_NAMES: dict[str, set] = {}   # deck_id -> set of card names (built once)


def _deck_name_sets() -> dict[str, set]:
    global _DECK_NAMES
    if not _DECK_NAMES:
        from data.cards_db import DECKS
        for did, builder in DECKS.items():
            try:
                _DECK_NAMES[did] = {c.name for c in builder()}
            except Exception:
                _DECK_NAMES[did] = set()
    return _DECK_NAMES


def opponent_public_names(engine: GameEngine, me: int) -> list[str]:
    """Card names the opponent has revealed (in play + evolution chains + discard)."""
    opp = engine.state.players[1 - me]
    names: list[str] = []
    for poke in opp.all_pokemon():
        names.append(poke.card.name)
        for base in poke.evolved_from:
            names.append(base.name)
    for c in opp.discard:
        names.append(c.card.name)
    return names


def infer_posterior(observed: list[str], beta: float = 1.6) -> dict[str, float]:
    """Softmax over how many distinct observed names appear in each deck."""
    decks = _deck_name_sets()
    distinct = set(observed)
    if not distinct:
        u = 1.0 / len(decks)
        return {d: u for d in decks}
    raw = {d: len(distinct & names) for d, names in decks.items()}
    if max(raw.values(), default=0) == 0:
        u = 1.0 / len(decks)
        return {d: u for d in decks}
    weights = {d: math.exp(beta * n) for d, n in raw.items()}
    z = sum(weights.values())
    return {d: w / z for d, w in weights.items()}


class MindReaderAgent(Agent):
    name = "mindreader"

    def __init__(self, rng: Optional[random.Random] = None, confidence: float = 0.34):
        self.rng = rng or random.Random()
        self.confidence = confidence            # min posterior to commit to a counter
        self._balanced = ClosingAgent(HeuristicAgent(self.rng))
        self._by_style: dict[str, ClosingAgent] = {}
        self.last_explanation = ""

    def _plan(self, style: str) -> ClosingAgent:
        if style not in self._by_style:
            self._by_style[style] = ClosingAgent(make_strategy_agent(style, self.rng))
        return self._by_style[style]

    def select(self, engine: GameEngine) -> Action:
        me = engine.state.current_player
        post = infer_posterior(opponent_public_names(engine, me))
        top = max(post, key=post.get)
        conf = post[top]

        from data.cards_db import DECK_META
        from data.deck_select import _style_of_archetype
        archetype = DECK_META.get(top, {}).get("archetype", "")
        opp_style = _style_of_archetype(archetype)

        if conf < self.confidence:
            self.last_explanation = (
                f"Opponent unclear ({conf:.0%} {top}); playing balanced."
            )
            return self._balanced.select(engine)

        counter = _COUNTER.get(opp_style, "setup")
        self.last_explanation = (
            f"Read: {top} — {archetype} ({conf:.0%}); countering with {counter}."
        )
        return self._plan(counter).select(engine)
