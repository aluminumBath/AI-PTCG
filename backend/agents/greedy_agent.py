"""Greedy (one-ply) agent.

The simplest principled search: evaluate the board state each legal move would
leave behind with the shared static evaluation, and take the best one — no
opponent reply, no rollouts. It sits between the hand-authored Heuristic and the
deeper Minimax: cheaper than Minimax, but unlike the rule-based Heuristic it acts
on a single numeric objective. A useful, fast baseline for the ladder.
"""
from __future__ import annotations

import random
from typing import Optional

from engine.game import GameEngine
from engine.actions import Action
from .basic_agents import Agent
from .minimax_agent import static_eval


class GreedyAgent(Agent):
    name = "greedy"

    def __init__(self, rng: Optional[random.Random] = None):
        self.rng = rng or random.Random()

    def select(self, engine: GameEngine) -> Action:
        actions = engine.legal_actions()
        if len(actions) == 1:
            return actions[0]
        me = engine.state.current_player
        best_val = float("-inf")
        best: list[Action] = []
        for a in actions:
            sim = engine.clone()
            sim.apply(a)
            v = static_eval(sim, me)
            if v > best_val:
                best_val, best = v, [a]
            elif v == best_val:
                best.append(a)
        return self.rng.choice(best)
