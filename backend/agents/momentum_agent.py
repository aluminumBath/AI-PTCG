"""Momentum — risk modulation by the prize race.

A human expert does not play the same way when ahead as when behind. This agent
makes that explicit: it reads the prize differential and shifts both its board
evaluation *and* how it prices risk.

* **Behind on prizes** (more of your own prizes left than the opponent's): you
  need variance. Tilt toward an aggressive plan and *reward* swingy, high-ceiling
  attacks (conditional / coin-flip / energy-scaling effects) — maximising P(win),
  not expected value.
* **Ahead**: protect the lead. Tilt toward a controlling plan and *penalise*
  risky attacks, preferring reliable damage and protecting the Active.
* **Even**: play a balanced midrange line.

Built on the same one-ply (clone → apply → opponent reply → score) machinery as
the strategy agents, so it stays fast and fully explainable.
"""
from __future__ import annotations

import random
from typing import Optional

from engine.actions import Action, ActionType
from engine.game import GameEngine
from .basic_agents import Agent, HeuristicAgent
from .heuristic_strategies import AGGRO, CONTROL, SETUP, Strategy, _score


def _attack_of(engine: GameEngine, a: Action):
    """The Attack object behind an ATTACK action, or None."""
    p = engine.state.current
    poke = p.active if (p.active and p.active.uid == a.source_uid) else None
    if poke is None:
        for cand in p.all_pokemon():
            if cand.uid == a.source_uid:
                poke = cand
                break
    if poke is None or a.sub_index is None or a.sub_index >= len(poke.card.attacks):
        return None
    return poke.card.attacks[a.sub_index]


def _risk_of(atk) -> float:
    """A transparent proxy for an attack's variance/ceiling. Effect-driven
    attacks (coin flips, conditional or energy-scaling damage, status) swing
    more than a flat-damage attack."""
    if atk is None:
        return 0.0
    risk = 0.0
    if atk.effect_id:
        risk += 1.0
    if atk.damage == 0 and atk.effect_id:   # pure-effect / all-or-nothing
        risk += 0.5
    return risk


class MomentumAgent(Agent):
    name = "momentum"

    def __init__(self, rng: Optional[random.Random] = None):
        self.rng = rng or random.Random()
        self._opp = HeuristicAgent(self.rng)
        self.last_explanation = ""

    def _regime(self, prize_diff: int) -> tuple[Strategy, float]:
        """Pick base weights + a risk coefficient from the prize differential
        (>0 ⇒ behind, <0 ⇒ ahead). Risk coefficient is signed: positive seeks
        variance, negative avoids it, and it grows with the size of the gap."""
        if prize_diff > 0:        # behind → seek variance
            return AGGRO, 18.0 * prize_diff
        if prize_diff < 0:        # ahead → suppress variance
            return CONTROL, 18.0 * prize_diff   # negative
        return SETUP, 0.0         # even → balanced midrange

    def select(self, engine: GameEngine) -> Action:
        actions = engine.legal_actions()
        if len(actions) == 1:
            return actions[0]
        me = engine.state.current_player
        mine, opp = engine.state.players[me], engine.state.players[1 - me]
        prize_diff = len(mine.prizes) - len(opp.prizes)   # >0 ⇒ behind
        strat, risk_coef = self._regime(prize_diff)

        best: list[Action] = []
        best_val = float("-inf")
        for a in actions:
            sim = engine.clone()
            sim.apply(a)
            guard = 0
            while (not sim.state.is_over() and sim.state.current_player != me
                   and guard < 60):
                sim.apply(self._opp.select(sim))
                guard += 1
            v = _score(sim, me, strat) + strat.bias.get(a.type, 0.0)
            if a.type == ActionType.ATTACK:
                v += risk_coef * _risk_of(_attack_of(engine, a))
            v += self.rng.random() * 0.01
            if v > best_val:
                best_val, best = v, [a]
            elif v == best_val:
                best.append(a)

        mp, op = len(mine.prizes), len(opp.prizes)
        stance = ("behind → high-variance aggro" if prize_diff > 0
                  else "ahead → safe control" if prize_diff < 0
                  else "even → balanced")
        self.last_explanation = f"Prizes {mp}–{op} ({stance})."
        return self.rng.choice(best)
