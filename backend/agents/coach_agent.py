"""The Coach — an LLM-advised, explainable agent.

Now that card text lives in the database, an agent can ask a language model to
reason about the position in natural language. The Coach describes the board and
the legal actions, asks the model for the best action plus a one-line rationale,
validates the choice against the legal set, and plays it — exposing the rationale
for the Watch / Coach view.

It is deliberately robust: if no API key is configured, the call times out, or
anything fails to parse, it falls back to the Heuristic agent and still produces
a rationale. That also makes it correct for the offline Kaggle Simulation
environment (no network) — there it simply *is* the heuristic, with explanations.

Config: ``ANTHROPIC_API_KEY`` (enables the LLM), ``COACH_MODEL`` (default
``claude-haiku-4-5``), ``COACH_TIMEOUT`` seconds (default 8).
"""
from __future__ import annotations

import json
import os
import random
from typing import Optional

from engine.actions import Action, ActionType
from engine.game import GameEngine
from .basic_agents import Agent, HeuristicAgent

_MAX_ACTIONS = 24   # keep the prompt small; above this, just use the heuristic


def _poke_line(p) -> str:
    bits = []
    if p.active:
        a = p.active
        bits.append(f"Active {a.card.name} {a.remaining_hp}/{a.card.hp}hp "
                    f"{a.energy_count()}E")
    bench = ", ".join(f"{b.card.name}({b.remaining_hp}hp)" for b in p.bench)
    if bench:
        bits.append("Bench: " + bench)
    return "; ".join(bits) or "empty"


def describe_state(engine: GameEngine, me: int) -> str:
    s = engine.state
    mine, opp = s.players[me], s.players[1 - me]
    lines = [
        f"Turn {s.turn_number}. Prizes left — you {len(mine.prizes)}, opp {len(opp.prizes)}.",
        f"You: {_poke_line(mine)}. Hand: {len(mine.hand)} cards.",
        f"Opponent: {_poke_line(opp)}.",
    ]
    if mine.active and mine.active.card.attacks:
        atk_bits = []
        for atk in mine.active.card.attacks:
            tag = " (effect)" if atk.effect_id else ""
            atk_bits.append(f"{atk.name} {atk.damage}dmg/{atk.cost_size}E{tag}")
        lines.append("Your active's attacks: " + "; ".join(atk_bits))
    return "\n".join(lines)


def _action_label(engine: GameEngine, a: Action) -> str:
    if a.type == ActionType.ATTACK:
        p = engine.state.current
        if p.active and a.sub_index is not None and a.sub_index < len(p.active.card.attacks):
            return f"Attack with {p.active.card.attacks[a.sub_index].name}"
    return a.describe()


class CoachAgent(Agent):
    name = "coach"

    def __init__(self, rng: Optional[random.Random] = None):
        self.rng = rng or random.Random()
        self._fallback = HeuristicAgent(self.rng)
        self.model = os.environ.get("COACH_MODEL", "claude-haiku-4-5")
        self.timeout = float(os.environ.get("COACH_TIMEOUT", "8"))
        self.last_explanation = ""

    # -- prompt + parsing (pure, unit-testable) ----------------------------- #
    def build_prompt(self, engine: GameEngine, actions: list[Action]) -> str:
        me = engine.state.current_player
        listing = "\n".join(f"{i}: {_action_label(engine, a)}" for i, a in enumerate(actions))
        return (
            "You are an expert Pokémon TCG player choosing this turn's next single action.\n"
            "Attacking ends your turn, so develop the board first unless an attack is lethal.\n\n"
            f"{describe_state(engine, me)}\n\nLegal actions:\n{listing}\n\n"
            'Reply with ONLY JSON: {"action": <index>, "why": "<short reason>"}.'
        )

    def parse_choice(self, text: str, n: int) -> Optional[tuple[int, str]]:
        try:
            start, end = text.find("{"), text.rfind("}")
            obj = json.loads(text[start:end + 1])
            idx = int(obj["action"])
            if 0 <= idx < n:
                return idx, str(obj.get("why", ""))[:200]
        except Exception:
            return None
        return None

    # -- LLM call (best-effort) --------------------------------------------- #
    def _ask_llm(self, prompt: str) -> Optional[str]:
        # Hard offline switch for competition submissions: PTCG_OFFLINE=1 disables
        # all network use regardless of whether a key happens to be present, so the
        # agent is provably offline on Kaggle. (It also no-ops without a key.)
        if os.environ.get("PTCG_OFFLINE"):
            return None
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            return None
        try:
            import urllib.request
            body = json.dumps({
                "model": self.model,
                "max_tokens": 200,
                "temperature": 0,
                "messages": [{"role": "user", "content": prompt}],
            }).encode()
            req = urllib.request.Request(
                "https://api.anthropic.com/v1/messages", data=body, method="POST",
                headers={"content-type": "application/json", "x-api-key": key,
                         "anthropic-version": "2023-06-01"},
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode())
            parts = data.get("content", [])
            return "".join(p.get("text", "") for p in parts if p.get("type") == "text")
        except Exception:
            return None

    def select(self, engine: GameEngine) -> Action:
        actions = engine.legal_actions()
        if len(actions) == 1:
            return actions[0]

        if len(actions) <= _MAX_ACTIONS:
            answer = self._ask_llm(self.build_prompt(engine, actions))
            if answer:
                choice = self.parse_choice(answer, len(actions))
                if choice:
                    idx, why = choice
                    self.last_explanation = f"Coach: {why}" if why else "Coach (LLM) chose this move."
                    return actions[idx]

        # Fallback: heuristic, with a rationale.
        a = self._fallback.select(engine)
        self.last_explanation = (
            "Coach (offline heuristic): "
            + ("taking lethal/biggest attack." if a.type == ActionType.ATTACK
               else f"developing — {a.type.value.replace('_', ' ')}.")
        )
        return a
