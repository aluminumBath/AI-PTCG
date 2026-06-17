"""Agents.

All agents implement ``select(engine) -> Action``. They only ever see what the
engine exposes via ``legal_actions`` and ``state``, so every agent is bound by
the same faithful rules.
"""
from __future__ import annotations

import random
from typing import Optional

from engine.actions import Action, ActionType
from engine.game import GameEngine


class Agent:
    name = "agent"

    def select(self, engine: GameEngine) -> Action:
        raise NotImplementedError


class RandomAgent(Agent):
    name = "random"

    def __init__(self, rng: Optional[random.Random] = None):
        self.rng = rng or random.Random()

    def select(self, engine: GameEngine) -> Action:
        actions = engine.legal_actions()
        # Avoid ending the turn immediately if more interesting moves exist.
        non_end = [a for a in actions if a.type != ActionType.END_TURN]
        pool = non_end if non_end and self.rng.random() < 0.85 else actions
        return self.rng.choice(pool)


class HeuristicAgent(Agent):
    """A solid rules-aware baseline: develop board, attach energy, attack for
    lethal/most damage, and use gust to snipe finishers. Good enough to be a
    real sparring partner for the RL policy and the MCTS agent."""

    name = "heuristic"

    def __init__(self, rng: Optional[random.Random] = None):
        self.rng = rng or random.Random()

    def select(self, engine: GameEngine) -> Action:
        actions = engine.legal_actions()
        s = engine.state
        me = s.current

        # Key insight: attacking ENDS the turn, so develop fully first and
        # attack last — unless an attack is lethal, in which case take it now.
        def score(a: Action) -> float:
            if a.type == ActionType.CHOOSE_ACTIVE:
                return 10_000  # forced promotion
            if a.type == ActionType.ATTACK:
                atk = me.active.card.attacks[a.sub_index]
                dmg = engine._compute_damage(me.active, s.opponent.active, atk) \
                    if s.opponent.active else atk.damage
                opp_active = s.opponent.active
                lethal = opp_active and dmg >= opp_active.remaining_hp
                # Lethal -> take immediately; otherwise attack only after
                # development (low base), preferring the biggest hit.
                return (9_000 + dmg) if lethal else (100 + dmg * 0.1)
            if a.type == ActionType.EVOLVE:
                return 900
            if a.type == ActionType.USE_ABILITY:
                return 800
            if a.type == ActionType.ATTACH_ENERGY:
                tgt = a.target_uid
                on_active = me.active and tgt == me.active.uid
                return 700 + (60 if on_active else 0)
            if a.type == ActionType.PLAY_SUPPORTER:
                return 600
            if a.type == ActionType.PLAY_BASIC:
                return 500
            if a.type == ActionType.PLAY_ITEM:
                return 400
            if a.type == ActionType.ATTACH_TOOL:
                return 350
            if a.type == ActionType.RETREAT:
                if me.active and me.active.remaining_hp < me.active.card.hp * 0.35:
                    return 300
                return -10
            if a.type == ActionType.END_TURN:
                return 1
            return 50

        actions.sort(key=score, reverse=True)
        return actions[0]
