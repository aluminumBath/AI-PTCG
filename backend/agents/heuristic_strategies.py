"""Alternative heuristic *strategies*.

The base `heuristic` agent plays one sensible line. These agents play to
different game plans by scoring the board each move leaves behind with a
strategy-specific set of weights, plus a small per-action-type bias. They share
one engine (`ScoredHeuristicAgent`) but express very different intentions:

* **aggro** — race for prizes: reward lowering the opponent's HP and taking
  prizes, barely value its own HP, and strongly prefer attacking.
* **control** — out-sustain the opponent: reward its own board HP, a wide bench
  and rule-box attackers (Potion/heal raise this score), and attack only when it
  clearly improves the position.
* **setup** — build before committing: reward energy in play, evolutions, a wide
  bench and rule-box Pokémon, and prefer attaching/evolving/abilities early.

All three are one-ply (clone, apply, score), so they're fast enough for the
ladder and the arena.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional

from engine.actions import Action, ActionType
from engine.game import GameEngine
from .basic_agents import Agent


@dataclass
class Strategy:
    name: str
    label: str
    description: str
    w_prize: float = 120.0       # prizes taken (mine good, opponent's bad)
    w_my_hp: float = 0.20        # HP remaining across my Pokémon
    w_opp_hp: float = 0.20       # HP across opponent's Pokémon (subtracted)
    w_opp_active_hp: float = 0.0 # extra reward for lowering the opp Active's HP
    w_energy: float = 8.0        # energy attached across my Pokémon
    w_rulebox: float = 10.0      # my Pokémon ex / rule-box in play
    w_bench: float = 0.0         # how wide my bench is
    w_status: float = 0.0        # Special Conditions on the opp Active (I want them)
    w_no_active: float = 50.0    # penalty for having no Active
    bias: dict = field(default_factory=dict)  # ActionType -> additive nudge


def _score(engine: GameEngine, me: int, st: Strategy) -> float:
    s = engine.state
    if s.is_over():
        if s.winner == me:
            return 1e6
        if s.winner is not None:
            return -1e6
    mine = s.players[me]
    opp = s.players[1 - me]
    score = 0.0
    score += (6 - len(mine.prizes)) * st.w_prize
    score -= (6 - len(opp.prizes)) * st.w_prize
    for poke in mine.all_pokemon():
        score += poke.remaining_hp * st.w_my_hp
        score += poke.energy_count() * st.w_energy
        score += st.w_rulebox if poke.card.rule_box else 0
    for poke in opp.all_pokemon():
        score -= poke.remaining_hp * st.w_opp_hp
    score += st.w_bench * len(mine.bench)
    score += 5 if mine.active else -st.w_no_active
    if opp.active:
        score -= opp.active.remaining_hp * st.w_opp_active_hp
        score += len(opp.active.status) * st.w_status
    return score


class ScoredHeuristicAgent(Agent):
    def __init__(self, strategy: Strategy, rng: Optional[random.Random] = None):
        self.strategy = strategy
        self.name = strategy.name
        self.rng = rng or random.Random()
        from .basic_agents import HeuristicAgent
        self._opp = HeuristicAgent(self.rng)  # models the opponent's reply

    def select(self, engine: GameEngine) -> Action:
        actions = engine.legal_actions()
        if len(actions) == 1:
            return actions[0]
        me = engine.state.current_player
        best: list[Action] = []
        best_val = float("-inf")
        for a in actions:
            sim = engine.clone()
            sim.apply(a)
            # If the move ended our turn, let the opponent answer before judging,
            # so the strategy weights act on a grounded position (this is what
            # stops the aggressive plan from attacking into an obvious punish).
            guard = 0
            while (not sim.state.is_over() and sim.state.current_player != me
                   and guard < 60):
                sim.apply(self._opp.select(sim))
                guard += 1
            v = _score(sim, me, self.strategy) + self.strategy.bias.get(a.type, 0.0)
            v += self.rng.random() * 0.01  # break ties without bias
            if v > best_val:
                best_val, best = v, [a]
            elif v == best_val:
                best.append(a)
        return self.rng.choice(best)


AGGRO = Strategy(
    name="aggro", label="Aggressive",
    description="Races for prizes — maximises damage to the opponent and attacks at every chance.",
    w_prize=140.0, w_my_hp=0.13, w_opp_hp=0.32, w_opp_active_hp=0.40,
    w_energy=5.0, w_rulebox=8.0, w_bench=2.0, w_status=8.0,
    bias={ActionType.ATTACK: 28.0, ActionType.END_TURN: -10.0},
)

CONTROL = Strategy(
    name="control", label="Control",
    description="Out-sustains the opponent — values board HP, a wide bench and healing over racing.",
    w_prize=110.0, w_my_hp=0.5, w_opp_hp=0.12, w_opp_active_hp=0.0,
    w_energy=9.0, w_rulebox=15.0, w_bench=14.0, w_status=3.0,
    bias={ActionType.ATTACK: 6.0, ActionType.PLAY_BASIC: 6.0, ActionType.RETREAT: 4.0},
)

SETUP = Strategy(
    name="setup", label="Setup / combo",
    description="Builds first — accelerates energy, evolves and widens the bench before committing to attacks.",
    w_prize=115.0, w_my_hp=0.2, w_opp_hp=0.12, w_opp_active_hp=0.05,
    w_energy=16.0, w_rulebox=18.0, w_bench=12.0, w_status=2.0,
    bias={ActionType.ATTACH_ENERGY: 14.0, ActionType.EVOLVE: 16.0,
          ActionType.PLAY_BASIC: 8.0, ActionType.USE_ABILITY: 12.0,
          ActionType.ATTACK: -6.0},
)

STRATEGIES = {s.name: s for s in (AGGRO, CONTROL, SETUP)}


def make_strategy_agent(name: str, rng: Optional[random.Random] = None) -> ScoredHeuristicAgent:
    return ScoredHeuristicAgent(STRATEGIES[name], rng)
