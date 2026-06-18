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


def _greedy_factory():
    def make(**_):
        from .greedy_agent import GreedyAgent
        return GreedyAgent()
    return make


def _strategy_factory(name: str):
    def make(**_):
        from .heuristic_strategies import make_strategy_agent
        return make_strategy_agent(name)
    return make


def _council_factory():
    def make(checkpoint=None, **_):
        from .ensemble_agents import build_council
        return build_council(checkpoint)
    return make


def _prime_factory():
    def make(checkpoint=None, **_):
        from .ensemble_agents import PrimeAgent
        return PrimeAgent(checkpoint)
    return make


def _meta_top3_factory():
    def make(checkpoint=None, **_):
        from .ensemble_agents import MetaTop3Agent
        return MetaTop3Agent(checkpoint)
    return make


def _flat_mc_factory(samples: int = 12):
    def make(**_):
        from .flat_mc_agent import FlatMonteCarloAgent
        return FlatMonteCarloAgent(samples=samples)
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
    "greedy": {
        "label": "Greedy (1-ply)",
        "family": "search",
        "description": "Takes the move that leaves the best-evaluated board — no opponent reply. A fast, principled baseline.",
        "factory": _greedy_factory(),
        "speed": "fast",
    },
    "aggro": {
        "label": "Aggressive",
        "family": "rule-based",
        "description": "Heuristic that races for prizes: maximises damage to the opponent and attacks at every opportunity.",
        "factory": _strategy_factory("aggro"),
        "speed": "fast",
    },
    "control": {
        "label": "Control",
        "family": "rule-based",
        "description": "Heuristic that out-sustains the opponent: values board HP, a wide bench and healing over racing.",
        "factory": _strategy_factory("control"),
        "speed": "fast",
    },
    "setup": {
        "label": "Setup / combo",
        "family": "rule-based",
        "description": "Heuristic that builds first: accelerates energy, evolves and widens the bench before committing.",
        "factory": _strategy_factory("setup"),
        "speed": "fast",
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
    "flat_mc": {
        "label": "Flat Monte-Carlo",
        "family": "search",
        "description": "Monte-Carlo evaluation: averages full rollouts per move and picks the best — flat sampling, no tree.",
        "factory": _flat_mc_factory(12),
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
    "council": {
        "label": "Council (all agents)",
        "family": "ensemble",
        "description": "Combines every model: each casts a weighted vote and the plurality move is played.",
        "factory": _council_factory(),
        "speed": "slow",
    },
    "prime": {
        "label": "Prime (best traits)",
        "family": "ensemble",
        "description": "Weighted vote of only the strongest models (learned + search + hidden-info + rule-based) with a Minimax safety veto.",
        "factory": _prime_factory(),
        "speed": "slow",
    },
    "meta_top3": {
        "label": "Meta — top 3 (dynamic)",
        "family": "ensemble",
        "description": "Votes among the current top-3 models on the scoreboard leaderboard, re-resolving whenever it changes.",
        "factory": _meta_top3_factory(),
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
