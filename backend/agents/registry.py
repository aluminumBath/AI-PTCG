"""Agent registry.

A single source of truth mapping an agent id -> {label, family, description,
factory}. The API, tournament engine, and UI all read from here, so adding a new
"model" in one place makes it available everywhere (game modes, the model arena,
the dropdowns).
"""
from __future__ import annotations

import os
from typing import Callable

from .basic_agents import Agent, RandomAgent, HeuristicAgent


def _mcts_factory(iterations: int = 120):
    def make(**_):
        from .mcts_agent import MCTSAgent
        return MCTSAgent(iterations=iterations)
    return make


def _rl_factory(temperature: float = 0.0):
    def make(checkpoint: str | None = None, **_):
        try:
            from rl.agent import RLAgent
            return RLAgent(checkpoint, temperature=temperature)
        except Exception:
            return HeuristicAgent()
    return make


def _minimax_factory(depth: int = 1):
    def make(**_):
        from .minimax_agent import MinimaxAgent
        return MinimaxAgent(opponent_reply=True)
    return make


def _rl_mcts_factory(iterations: int = 120):
    def make(checkpoint: str | None = None, **_):
        try:
            from .rl_mcts_agent import RLGuidedMCTSAgent
            return RLGuidedMCTSAgent(iterations=iterations, checkpoint=checkpoint)
        except Exception:
            from .mcts_agent import MCTSAgent
            return MCTSAgent(iterations=iterations)
    return make


def _ismcts_factory(iterations: int = 160):
    def make(**_):
        from .ismcts_agent import ISMCTSAgent
        return ISMCTSAgent(iterations=iterations)
    return make


# id -> metadata + factory. ``family`` groups algorithms for the UI.
REGISTRY: dict[str, dict] = {
    "random": {
        "label": "Random",
        "family": "baseline",
        "description": "Picks a legal move at random. The noise floor.",
        "factory": lambda **_: RandomAgent(),
        "speed": "instant",
    },
    "heuristic": {
        "label": "Heuristic",
        "family": "rule-based",
        "description": "Hand-tuned priorities: develop the board, then attack for lethal.",
        "factory": lambda **_: HeuristicAgent(),
        "speed": "instant",
    },
    "minimax": {
        "label": "Minimax (lookahead)",
        "family": "search",
        "description": "Evaluates each move by the board it leaves behind, anticipating the opponent's reply.",
        "factory": _minimax_factory(),
        "speed": "fast",
    },
    "mcts": {
        "label": "MCTS",
        "family": "search",
        "description": "Monte-Carlo Tree Search with heuristic rollouts. Plans several moves ahead.",
        "factory": _mcts_factory(120),
        "speed": "slow",
    },
    "ismcts": {
        "label": "ISMCTS (imperfect-info)",
        "family": "search",
        "description": "Information-Set MCTS: re-samples hidden cards each iteration instead of peeking. Built for imperfect information.",
        "factory": _ismcts_factory(140),
        "speed": "slow",
    },
    "rl": {
        "label": "RL policy",
        "family": "learned",
        "description": "PPO self-play policy/value network, played greedily.",
        "factory": _rl_factory(0.0),
        "speed": "fast",
    },
    "rl_mcts": {
        "label": "RL + MCTS",
        "family": "hybrid",
        "description": "MCTS that evaluates leaves with the trained value network (AlphaZero-style).",
        "factory": _rl_mcts_factory(120),
        "speed": "slow",
    },
}


def list_agents() -> list[dict]:
    return [
        {"id": k, "label": v["label"], "family": v["family"],
         "description": v["description"], "speed": v["speed"]}
        for k, v in REGISTRY.items()
    ]


def make_agent(agent_id: str, checkpoint: str | None = None) -> Agent:
    meta = REGISTRY.get(agent_id)
    if not meta:
        return HeuristicAgent()
    return meta["factory"](checkpoint=checkpoint)
