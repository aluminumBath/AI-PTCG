"""Ensemble / meta agents.

Three agents that *combine* the others:

* **council**  — combines all the agents: every non-random model casts a
  weighted vote for its preferred move and the plurality move is played.
* **prime**    — combines the *best traits*: a weighted vote of only the
  strongest models (learned + search + hidden-info + rule-based) wrapped in a
  Minimax-style safety veto so it never votes into an obvious punish.
* **meta_top3** — dynamic: reads the current scoreboard leaderboard and forms a
  weighted vote of the **top 3 models**, re-resolving whenever the leaderboard
  changes (short TTL cache).

All voting maps each member's chosen action to a canonical key so equivalent
moves combine, then returns a real legal Action.
"""
from __future__ import annotations

import random
import time
from typing import Callable, Optional

from engine.actions import Action
from engine.game import GameEngine
from .basic_agents import Agent, HeuristicAgent

# meta agents may never be voting members (avoid recursion); random adds noise.
_EXCLUDE_FROM_ENSEMBLES = {"random", "council", "prime", "meta_top3"}


def _key(a: Action):
    return (a.type, a.hand_index, a.source_uid, a.target_uid, a.sub_index)


def make_member(mid: str, checkpoint: Optional[str], rng: random.Random,
                light: bool = True) -> Agent:
    """Build a member agent, giving the search models a smaller budget when
    `light` so an ensemble stays responsive (it runs several agents per move)."""
    from .registry import make_agent
    if not light:
        return make_agent(mid, checkpoint)
    if mid == "mcts":
        from .mcts_agent import MCTSAgent
        return MCTSAgent(iterations=40, rollout_depth=24, rng=rng)
    if mid == "ismcts":
        from .ismcts_agent import ISMCTSAgent
        return ISMCTSAgent(iterations=40, determinizations=4, rollout_depth=24, rng=rng)
    if mid == "flat_mc":
        from .flat_mc_agent import FlatMonteCarloAgent
        return FlatMonteCarloAgent(samples=8, rollout_depth=24, rng=rng)
    if mid == "rl_mcts":
        try:
            from .rl_mcts_agent import RLMCTSAgent
            return RLMCTSAgent(iterations=50, checkpoint=checkpoint, rng=rng)
        except Exception:
            from .mcts_agent import MCTSAgent
            return MCTSAgent(iterations=40, rollout_depth=24, rng=rng)
    return make_agent(mid, checkpoint)  # random/heuristic/greedy/aggro/control/setup/minimax/rl


class VotingEnsembleAgent(Agent):
    """Weighted plurality vote over member agents."""

    def __init__(self, members: list[tuple[Agent, float]], name: str,
                 anchor: int = 0, rng: Optional[random.Random] = None):
        self.members = members
        self.name = name
        self.anchor = anchor  # index whose pick wins ties
        self.rng = rng or random.Random()

    def _vote(self, engine: GameEngine, legal: list[Action]) -> Action:
        tally: dict = {}
        pick: dict = {}
        anchor_key = None
        for i, (agent, w) in enumerate(self.members):
            try:
                a = agent.select(engine)
            except Exception:
                continue
            k = _key(a)
            tally[k] = tally.get(k, 0.0) + w
            pick.setdefault(k, a)
            if i == self.anchor:
                anchor_key = k
        if not tally:
            return self.rng.choice(legal)
        best = max(tally.values())
        winners = [k for k, v in tally.items() if v == best]
        if anchor_key in winners:          # break ties toward the strongest member
            return pick[anchor_key]
        return pick[winners[0]]

    def select(self, engine: GameEngine) -> Action:
        legal = engine.legal_actions()
        if len(legal) == 1:
            return legal[0]
        return self._vote(engine, legal)


def build_council(checkpoint: Optional[str] = None,
                  rng: Optional[random.Random] = None) -> VotingEnsembleAgent:
    rng = rng or random.Random()
    ids_weights = [
        ("heuristic", 1.0), ("greedy", 0.7),
        ("aggro", 0.6), ("control", 0.6), ("setup", 0.6),
        ("minimax", 1.0), ("flat_mc", 0.8), ("mcts", 1.3),
        ("ismcts", 1.6), ("rl", 1.4), ("rl_mcts", 1.7),
    ]
    members = [(make_member(mid, checkpoint, rng), w) for mid, w in ids_weights]
    anchor = next((i for i, (mid, _) in enumerate(ids_weights) if mid == "rl_mcts"), 0)
    return VotingEnsembleAgent(members, name="council", anchor=anchor, rng=rng)


class PrimeAgent(Agent):
    """Best-traits hybrid: a weighted vote of the strongest models, guarded by a
    one-ply opponent-reply (Minimax) safety check so it never commits to a move
    that hands the opponent a clearly better position when a safer move exists."""

    name = "prime"

    def __init__(self, checkpoint: Optional[str] = None,
                 rng: Optional[random.Random] = None, margin: float = 120.0):
        self.rng = rng or random.Random()
        self.margin = margin
        self._heur = HeuristicAgent(self.rng)
        ids_weights = [("rl_mcts", 2.0), ("ismcts", 1.8), ("rl", 1.3), ("heuristic", 1.0)]
        members = [(make_member(mid, checkpoint, self.rng), w) for mid, w in ids_weights]
        self._vote = VotingEnsembleAgent(members, name="prime-core", anchor=0, rng=self.rng)

    def _grounded_value(self, engine: GameEngine, action: Action, me: int) -> float:
        from .minimax_agent import static_eval
        sim = engine.clone()
        sim.apply(action)
        guard = 0
        while (not sim.state.is_over() and sim.state.current_player != me and guard < 60):
            sim.apply(self._heur.select(sim))
            guard += 1
        return static_eval(sim, me)

    def select(self, engine: GameEngine) -> Action:
        legal = engine.legal_actions()
        if len(legal) == 1:
            return legal[0]
        me = engine.state.current_player
        chosen = self._vote._vote(engine, legal)
        safe = self._heur.select(engine)
        if _key(safe) == _key(chosen):
            return chosen
        # veto: only override if the heuristic's move is clearly safer
        if self._grounded_value(engine, safe, me) > self._grounded_value(engine, chosen, me) + self.margin:
            return safe
        return chosen


def default_leaderboard() -> list[str]:
    """Current model ranking from the scoreboard (best first), restricted to
    eligible base models. Falls back to a sensible order before any games."""
    try:
        from stats.model_stats import list_stats
        ranked = [r["model"] for r in list_stats()
                  if r.get("games", 0) > 0 and r["model"] not in _EXCLUDE_FROM_ENSEMBLES]
    except Exception:
        ranked = []
    fallback = ["rl_mcts", "ismcts", "heuristic", "minimax", "rl", "mcts"]
    for mid in fallback:
        if mid not in ranked:
            ranked.append(mid)
    return ranked


class MetaTop3Agent(Agent):
    """Dynamically votes among the current top-3 models on the leaderboard,
    re-resolving when the leaderboard changes (TTL-cached)."""

    name = "meta_top3"

    def __init__(self, checkpoint: Optional[str] = None,
                 rng: Optional[random.Random] = None,
                 leaderboard_fn: Optional[Callable[[], list[str]]] = None,
                 ttl: float = 5.0):
        self.checkpoint = checkpoint
        self.rng = rng or random.Random()
        self.leaderboard_fn = leaderboard_fn or default_leaderboard
        self.ttl = ttl
        self._cached_ids: list[str] = []
        self._vote: Optional[VotingEnsembleAgent] = None
        self._stamp = 0.0

    def current_top3(self) -> list[str]:
        return list(self._cached_ids)

    def _ensure(self):
        now = time.time()
        if self._vote is not None and now - self._stamp < self.ttl:
            return
        top3 = self.leaderboard_fn()[:3] or ["rl_mcts", "ismcts", "heuristic"]
        if top3 != self._cached_ids or self._vote is None:
            weights = [1.5, 1.2, 1.0][:len(top3)]
            members = [(make_member(mid, self.checkpoint, self.rng), w)
                       for mid, w in zip(top3, weights)]
            self._vote = VotingEnsembleAgent(members, name="meta_top3", anchor=0, rng=self.rng)
            self._cached_ids = top3
        self._stamp = now

    def select(self, engine: GameEngine) -> Action:
        legal = engine.legal_actions()
        if len(legal) == 1:
            return legal[0]
        self._ensure()
        return self._vote._vote(engine, legal)
