"""Single-observer Information-Set MCTS (ISMCTS).

The PTCG is an *imperfect-information* game: you can't see the opponent's hand,
either deck's order, or the prize cards. Our plain MCTS determinizes over the
true state — i.e. it effectively peeks at hidden cards, which is both unfair and
unrealistic for the competition.

ISMCTS fixes this. Each search iteration *re-samples* a hidden state consistent
with everything the moving player can actually observe (public board, discards,
hand/deck/prize counts), then descends the shared tree on that determinization.
Aggregating over many determinizations yields a policy that is robust to what it
cannot see — the right model for this contest.

What's preserved each sample (public information):
  * both players' in-play Pokémon, attached cards, damage, status
  * both discard piles and the stadium
  * the observer's own hand
  * all zone *counts* (opponent hand size, deck sizes, prize counts)
What's re-shuffled (hidden):
  * the opponent's hand / deck / prize *placement* (from their known card pool)
  * the observer's own deck and prize ordering (hand stays fixed)
"""
from __future__ import annotations

import random
from typing import Optional

from engine.game import GameEngine
from .mcts_agent import MCTSAgent, _Node


def determinize(engine: GameEngine, observer: int, rng: random.Random) -> GameEngine:
    """Return a clone with hidden zones re-sampled consistently with what
    ``observer`` can see. In-play cards, discards and zone counts are untouched."""
    sim = engine.clone()
    for pi, p in enumerate(sim.state.players):
        if pi == observer:
            # We know our hand; our deck+prize ordering is hidden even to us.
            pool = p.deck + p.prizes
            rng.shuffle(pool)
            n_prizes = len(p.prizes)
            p.prizes = pool[:n_prizes]
            p.deck = pool[n_prizes:]
        else:
            # Opponent: hand, deck and prize placement are all hidden.
            pool = p.hand + p.deck + p.prizes
            rng.shuffle(pool)
            nh, npz = len(p.hand), len(p.prizes)
            p.hand = pool[:nh]
            p.prizes = pool[nh:nh + npz]
            p.deck = pool[nh + npz:]
    return sim


class ISMCTSAgent(MCTSAgent):
    name = "ismcts"

    def __init__(self, iterations: int = 160, rollout_depth: int = 40,
                 c: float = 1.4, determinizations: int = 8,
                 rng: Optional[random.Random] = None):
        super().__init__(iterations=iterations, rollout_depth=rollout_depth, c=c, rng=rng)
        self.determinizations = determinizations

    @staticmethod
    def _key(a):
        return (a.type, a.hand_index, a.source_uid, a.target_uid, a.sub_index)

    def select(self, engine: GameEngine):
        root_actions = engine.legal_actions()
        if len(root_actions) == 1:
            return root_actions[0]
        root_player = engine.state.current_player

        # Root-parallel determinization: an independent tree per hidden-state
        # sample, with visits aggregated at the root. The observer's own root
        # actions are identical across samples (their hand/board are observed),
        # so aggregation keys line up; only deeper, hidden dynamics differ.
        agg: dict = {}
        iters_per = max(20, self.iterations // self.determinizations)
        for _ in range(self.determinizations):
            base = determinize(engine, root_player, self.rng)
            root = _Node(player_to_move=root_player, untried=list(base.legal_actions()))
            for _ in range(iters_per):
                sim = base.clone()
                node = self._tree_policy(root, sim, root_player)
                reward = self._rollout(sim, root_player)
                self._backprop(node, reward)
            for ch in root.children:
                slot = agg.setdefault(self._key(ch.action_from_parent),
                                      [ch.action_from_parent, 0, 0.0])
                slot[1] += ch.visits
                slot[2] += ch.value

        if not agg:
            return root_actions[0]
        best = max(agg.values(), key=lambda s: s[1])
        return best[0]
