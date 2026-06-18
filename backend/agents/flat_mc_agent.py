"""Flat Monte-Carlo agent (Monte-Carlo evaluation, no tree).

For each legal move, play out several full random/heuristic rollouts and average
the win/draw/loss outcome; pick the move with the best average. Unlike MCTS there
is no selective tree or UCT — every action gets the same flat sampling budget.
This is the classic "Monte-Carlo evaluation" baseline and a distinct search
family from tree search, useful for comparison in the strategy report.
"""
from __future__ import annotations

import random
from typing import Optional

from engine.game import GameEngine
from engine.actions import Action
from .basic_agents import Agent
from .mcts_agent import MCTSAgent


class FlatMonteCarloAgent(Agent):
    name = "flat_mc"

    def __init__(self, samples: int = 12, rollout_depth: int = 40,
                 rng: Optional[random.Random] = None):
        self.samples = samples
        self.rng = rng or random.Random()
        # Reuse MCTS's tested rollout/reward machinery (heuristic playouts).
        self._mc = MCTSAgent(rollout_depth=rollout_depth, rng=self.rng)

    def select(self, engine: GameEngine) -> Action:
        actions = engine.legal_actions()
        if len(actions) == 1:
            return actions[0]
        me = engine.state.current_player
        best_val = float("-inf")
        best: list[Action] = []
        for a in actions:
            total = 0.0
            for _ in range(self.samples):
                sim = engine.clone()
                sim.apply(a)
                total += self._mc._rollout(sim, me)
            avg = total / self.samples
            if avg > best_val:
                best_val, best = avg, [a]
            elif avg == best_val:
                best.append(a)
        return self.rng.choice(best)
