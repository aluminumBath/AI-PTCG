"""RL-guided MCTS (AlphaZero-style, value-only).

Inherits the UCT search from ``MCTSAgent`` but replaces random/heuristic rollouts
with a single evaluation of the leaf state by the trained value network. This is
faster per node than rolling out to the end and grounds the search in learned
position evaluation — the "best of both" of the search and learned families.
"""
from __future__ import annotations

import math
from typing import Optional

from engine.game import GameEngine
from .mcts_agent import MCTSAgent


class RLGuidedMCTSAgent(MCTSAgent):
    name = "rl_mcts"

    def __init__(self, iterations: int = 120, rollout_depth: int = 6,
                 checkpoint: Optional[str] = None, **kwargs):
        super().__init__(iterations=iterations, rollout_depth=rollout_depth, **kwargs)
        # Raises if torch/checkpoint unavailable; the registry factory then
        # falls back to plain MCTS.
        from rl.agent import RLAgent
        self._rl = RLAgent(checkpoint, temperature=0.0)

    def _rollout(self, sim: GameEngine, root_player: int) -> float:
        if sim.state.is_over():
            return self._reward(sim, root_player)
        # Optional shallow rollout to get off the leaf, then bootstrap with V(s).
        depth = 0
        while not sim.state.is_over() and depth < self.rollout_depth:
            sim.apply(self._rollout_policy.select(sim))
            depth += 1
        if sim.state.is_over():
            return self._reward(sim, root_player)
        v = self._rl.value(sim)                      # current player's perspective
        if sim.state.current_player != root_player:
            v = -v
        return 1.0 / (1.0 + math.exp(-v))            # squash to (0, 1)
