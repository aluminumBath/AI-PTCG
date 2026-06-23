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


def _closer_factory():
    def make(**_):
        from .closer_agent import ClosingAgent
        return ClosingAgent(HeuristicAgent())
    return make


def _momentum_factory():
    def make(**_):
        from .momentum_agent import MomentumAgent
        return MomentumAgent()
    return make


def _mindreader_factory():
    def make(**_):
        from .mindreader_agent import MindReaderAgent
        return MindReaderAgent()
    return make


def _coach_factory():
    def make(**_):
        from .coach_agent import CoachAgent
        return CoachAgent()
    return make


def _coach_search_factory():
    def make(**_):
        from .coach_search_agent import SearchCoachAgent
        return SearchCoachAgent()
    return make


def _alphazero_factory(iterations: int = 300):
    def make(checkpoint: str | None = None, **_):
        try:
            from .alphazero_agent import AlphaZeroAgent
            return AlphaZeroAgent(checkpoint=checkpoint, iterations=iterations)
        except Exception:
            from .mcts_agent import MCTSAgent
            return MCTSAgent(iterations=max(200, iterations // 2))
    return make


def _closer_deep_factory():
    def make(**_):
        from .closer_agent import ClosingAgent
        return ClosingAgent(max_depth=5, budget=6000, trials=5)
    return make


def _neural_ismcts_factory(iterations: int = 200):
    def make(**_):
        try:
            from .neural_ismcts_agent import NeuralISMCTSAgent
            base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "checkpoints", "opponent_model.pt")
            mc = os.environ.get("OPPONENT_MODEL", base)
            return NeuralISMCTSAgent(model_checkpoint=mc, iterations=iterations)
        except Exception:
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
    "closer": {
        "label": "Closer (lethal solver)",
        "family": "hybrid",
        "description": "Wraps a base policy with an exhaustive, RNG-verified search for a winning line this turn — so it never misses a (possibly multi-step) lethal. Defers to the Heuristic when none exists.",
        "factory": _closer_factory(),
        "speed": "fast",
    },
    "momentum": {
        "label": "Momentum (risk-aware)",
        "family": "adaptive",
        "description": "Reads the prize race and modulates variance: aggressive and swingy when behind to maximise win probability, safe and controlling when ahead to protect the lead.",
        "factory": _momentum_factory(),
        "speed": "fast",
    },
    "mindreader": {
        "label": "Mind-reader (opponent inference)",
        "family": "adaptive",
        "description": "Infers the opponent's archetype from public play (a posterior over the 26 decks), then switches to the matchup-favoured counter-plan. Never misses lethal (runs through the Closer).",
        "factory": _mindreader_factory(),
        "speed": "fast",
    },
    "coach": {
        "label": "Coach (LLM-advised)",
        "family": "adaptive",
        "description": "Asks a language model to reason about the board and pick a move with a natural-language rationale (validated against the legal actions). Falls back to the Heuristic offline — e.g. on Kaggle — so it always plays.",
        "factory": _coach_factory(),
        "speed": "slow",
    },
    "coach_search": {
        "label": "Coach + search (propose-verify)",
        "family": "adaptive",
        "description": "An LLM proposes a shortlist of candidate moves; the engine simulates each and plays the one that actually scores best, with the model's reasoning as the rationale. Offline it degrades to a full one-ply search, never a guess. Never misses lethal.",
        "factory": _coach_search_factory(),
        "speed": "slow",
    },
    "alphazero": {
        "label": "AlphaZero (PUCT + net)",
        "family": "hybrid",
        "description": "Best-first PUCT tree search guided by the trained policy (action priors) and value head (leaf evaluation) — no random rollouts. Runs a guaranteed-lethal check first. Falls back to MCTS without a checkpoint.",
        "factory": _alphazero_factory(300),
        "speed": "slow",
    },
    "alphazero_deep": {
        "label": "AlphaZero — deep (900 sims)",
        "family": "hybrid",
        "description": "The AlphaZero PUCT agent with a much larger per-move simulation budget — practical when self-hosting (no 10-minute match cap). Stronger but slower.",
        "factory": _alphazero_factory(900),
        "speed": "slow",
    },
    "mcts_deep": {
        "label": "MCTS — deep (1200 iters)",
        "family": "search",
        "description": "Plain UCT MCTS with a much larger iteration budget for self-hosted, time-unconstrained play.",
        "factory": _mcts_factory(1200),
        "speed": "slow",
    },
    "ismcts_deep": {
        "label": "ISMCTS — deep (3500 iters)",
        "family": "search",
        "description": "Information-Set MCTS with a much larger iteration budget — stronger hidden-information play when there's no time limit.",
        "factory": _ismcts_factory(3500),
        "speed": "slow",
    },
    "rl_mcts_deep": {
        "label": "RL-MCTS — deep (1200 iters)",
        "family": "hybrid",
        "description": "Value-net-guided MCTS with a much larger iteration budget; falls back to deep MCTS without a checkpoint.",
        "factory": _rl_mcts_factory(1200),
        "speed": "slow",
    },
    "closer_deep": {
        "label": "Closer — deep (depth 5)",
        "family": "hybrid",
        "description": "The lethal solver with a deeper, larger search (depth 5, budget 6000, 6 verify seeds) for finding longer forced wins when time allows.",
        "factory": _closer_deep_factory(),
        "speed": "slow",
    },
    "neural_ismcts": {
        "label": "Neural ISMCTS (opponent model)",
        "family": "hybrid",
        "description": "ISMCTS whose determinizations are weighted by a learned opponent model predicting which cards the opponent holds — a learned 'deep mind-reader'. Falls back to uniform ISMCTS when no model is trained.",
        "factory": _neural_ismcts_factory(200),
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
