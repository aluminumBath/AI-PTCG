"""Minimax-style lookahead agent.

A different family from MCTS: instead of random rollouts, it scores each legal
move by the *board state it produces*, and for turn-ending moves it lets the
opponent take its (heuristic) reply first — so it won't swing into a position
that hands the opponent a knockout. A compact, deterministic adversarial search
with a static evaluation.
"""
from __future__ import annotations

import random
from typing import Optional

from engine.actions import Action, ActionType
from engine.game import GameEngine
from .basic_agents import Agent, HeuristicAgent


def static_eval(engine: GameEngine, me: int) -> float:
    """Score a state from player ``me``'s perspective. Higher is better."""
    s = engine.state
    if s.is_over():
        if s.winner == me:
            return 1e6
        if s.winner is not None:
            return -1e6
    mine = s.players[me]
    opp = s.players[1 - me]
    # Prizes are the win condition — weight them heavily (fewer remaining = good).
    score = (6 - len(mine.prizes)) * 100         # prizes I've taken
    score -= (6 - len(opp.prizes)) * 100          # prizes opponent has taken
    # Board presence
    for p, sign in ((mine, 1), (opp, -1)):
        for poke in p.all_pokemon():
            score += sign * (poke.remaining_hp * 0.2)
            score += sign * (poke.energy_count() * 8)
            score += sign * (10 if poke.card.rule_box else 0)
        score += sign * (5 if p.active else -50)  # no active is dire
    return score


class MinimaxAgent(Agent):
    name = "minimax"

    def __init__(self, opponent_reply: bool = True, rng: Optional[random.Random] = None):
        self.opponent_reply = opponent_reply
        self.rng = rng or random.Random()
        self._opp = HeuristicAgent(self.rng)

    def select(self, engine: GameEngine) -> Action:
        actions = engine.legal_actions()
        if len(actions) == 1:
            return actions[0]
        me = engine.state.current_player
        best, best_val = actions[0], float("-inf")
        for a in actions:
            sim = engine.clone()
            sim.apply(a)
            # If the move passed the turn, let the opponent answer before judging.
            if self.opponent_reply and sim.state.current_player != me and not sim.state.is_over():
                guard = 0
                while (not sim.state.is_over()
                       and sim.state.current_player != me and guard < 60):
                    sim.apply(self._opp.select(sim))
                    guard += 1
            val = static_eval(sim, me)
            # tiny tie-break noise so it isn't deterministic across equal moves
            val += self.rng.random() * 0.01
            if val > best_val:
                best, best_val = a, val
        return best
