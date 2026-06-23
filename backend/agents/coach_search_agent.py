"""Coach + search — the LLM proposes, the engine verifies.

A language model reads the position and proposes a short list of candidate moves;
the engine then *simulates* each candidate (apply it, let the opponent reply,
score the resulting board) and plays whichever actually scores best — with the
model's reasoning as the rationale. A guaranteed-lethal check runs first.

This is the "propose-and-verify" design (cf. PokéChamp's minimax language agent):
the LLM prunes a large action space and explains the plan, while simulation
guarantees the move is sound. Offline — no API key, or on Kaggle — it degrades to
a full one-ply search over every legal action, so it is never just a guess.
"""
from __future__ import annotations

import json
import random
from typing import Optional

from engine.game import GameEngine
from engine.actions import Action
from .basic_agents import Agent, HeuristicAgent
from .closer_agent import find_lethal, lethal_plausible
from .coach_agent import CoachAgent, describe_state, _action_label
from .heuristic_strategies import SETUP, _score

_MAX_ACTIONS_FOR_LLM = 28


def _value_of(engine: GameEngine, me: int, action: Action,
              opp: Agent, strat) -> float:
    """One-ply value: apply ``action``, let the opponent reply, score the board.
    Winning lines dominate; losing lines are pushed to the bottom."""
    sim = engine.clone()
    try:
        sim.apply(action)
    except Exception:
        return float("-inf")
    guard = 0
    while not sim.state.is_over() and sim.state.current_player != me and guard < 60:
        sim.apply(opp.select(sim))
        guard += 1
    if sim.state.is_over():
        return 1e6 if sim.state.winner == me else -1e6
    return _score(sim, me, strat)


class SearchCoachAgent(Agent):
    name = "coach_search"

    def __init__(self, rng: Optional[random.Random] = None):
        self.rng = rng or random.Random()
        self._opp = HeuristicAgent(self.rng)
        self._heur = HeuristicAgent(self.rng)
        self._llm = CoachAgent(self.rng)     # reuse its prompt + LLM plumbing
        self.last_explanation = ""

    def _shortlist_prompt(self, engine: GameEngine, actions: list[Action]) -> str:
        me = engine.state.current_player
        listing = "\n".join(f"{i}: {_action_label(engine, a)}" for i, a in enumerate(actions))
        return (
            "You are an expert Pokémon TCG player. From the legal actions, choose the 1-3 most "
            "promising to consider this turn (attacking ends your turn, so usually develop the "
            "board first unless an attack is lethal).\n\n"
            f"{describe_state(engine, me)}\n\nLegal actions:\n{listing}\n\n"
            'Reply with ONLY JSON: {"actions": [<indices, best first>], "why": "<short reason>"}.'
        )

    def _parse_shortlist(self, text: str, n: int) -> tuple[list[int], str]:
        try:
            s, e = text.find("{"), text.rfind("}")
            obj = json.loads(text[s:e + 1])
            why = str(obj.get("why", ""))[:200]
            out, seen = [], set()
            for i in obj.get("actions", []):
                if isinstance(i, (int, float)):
                    i = int(i)
                    if 0 <= i < n and i not in seen:
                        seen.add(i); out.append(i)
            return out[:4], why
        except Exception:
            return [], ""

    def select(self, engine: GameEngine) -> Action:
        actions = engine.legal_actions()
        if len(actions) == 1:
            return actions[0]
        me = engine.state.current_player

        # 1) never miss a forced win
        if lethal_plausible(engine, me):
            line = find_lethal(engine, me)
            if line:
                self.last_explanation = "Coach+search: forced lethal this turn."
                return line[0]

        # 2) LLM proposes a shortlist (when reachable and the action set is small)
        shortlist, why = [], ""
        if len(actions) <= _MAX_ACTIONS_FOR_LLM:
            answer = self._llm._ask_llm(self._shortlist_prompt(engine, actions))
            if answer:
                shortlist, why = self._parse_shortlist(answer, len(actions))

        if shortlist:
            cand = list(shortlist)
            try:                                   # always include a heuristic safety pick
                safe = actions.index(self._heur.select(engine))
                if safe not in cand:
                    cand.append(safe)
            except Exception:
                pass
            best = max(cand, key=lambda i: _value_of(engine, me, actions[i], self._opp, SETUP))
            chosen = _action_label(engine, actions[best])
            proposed = ", ".join(_action_label(engine, actions[i]) for i in shortlist)
            verdict = "confirmed" if best == shortlist[0] else "overrode → "
            self.last_explanation = (
                f"Coach+search: LLM proposed [{proposed}]; simulation {verdict}'{chosen}'."
                + (f" {why}" if why else "")
            )
            return actions[best]

        # 3) offline / no shortlist → full one-ply search over all actions
        best_i = max(range(len(actions)),
                     key=lambda i: _value_of(engine, me, actions[i], self._opp, SETUP))
        self.last_explanation = (
            f"Coach+search (offline 1-ply): chose '{_action_label(engine, actions[best_i])}'."
        )
        return actions[best_i]
