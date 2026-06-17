"""Simulation-Category agent entrypoint (integration seam).

The PTCG AI Battle Challenge Simulation Category runs your agent inside Kaggle's
hosted environment: it repeatedly calls your agent with an *observation* and
expects an *action* in the environment's own encoding. That exact schema (and
the competition's custom rule tweaks) live in the official starter notebook,
which is behind the competition's Code/Data tabs.

This module is the clean seam between that harness and our engine:

  observation (Kaggle schema)
        │  decode_observation()   ← FILL IN from the official starter code
        ▼
  our GameEngine state  ──►  model.select(engine)  ──►  our Action
        │  encode_action()       ← FILL IN from the official starter code
        ▼
  action (Kaggle schema)

The model selection, our rules engine, and the imperfect-information agents are
all production-ready; only the two translation functions need to be bound to the
official observation/action format. We default to the imperfect-information-safe
models (RL, then ISMCTS, then heuristic) since the contest is hidden-information.

Local use (no Kaggle): `choose_action` also accepts our own serialized state for
testing, and `agents.registry` powers the same models used in the app.
"""
from __future__ import annotations

import os
from typing import Any, Optional

from agents.registry import make_agent

# Preference order: learned policy first (II-safe and fast), then ISMCTS
# (II-aware search), then the heuristic as a guaranteed fallback.
DEFAULT_MODEL_ORDER = ["rl", "ismcts", "heuristic"]
_CKPT = os.environ.get(
    "RL_CHECKPOINT",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 "checkpoints", "policy_latest.pt"),
)


class KaggleAgent:
    """Holds a chosen model and translates between Kaggle and our engine."""

    def __init__(self, model: Optional[str] = None):
        self.model_id = model or os.environ.get("AGENT_MODEL") or DEFAULT_MODEL_ORDER[0]
        self.agent = make_agent(self.model_id, _CKPT)

    # ---- The two functions to bind to the official starter env ------------- #
    def decode_observation(self, observation: Any, configuration: Any):
        """Rebuild a GameEngine (or compatible state) from Kaggle's observation.

        TODO(official-starter): map the competition's observation fields onto our
        engine state. Until then this raises so failures are loud rather than
        silently wrong."""
        raise NotImplementedError(
            "Bind decode_observation() to the official PTCG-ABC starter schema."
        )

    def encode_action(self, action, observation: Any, configuration: Any):
        """Translate our engine Action into the competition's action encoding.

        TODO(official-starter): map our Action to the env's expected value."""
        raise NotImplementedError(
            "Bind encode_action() to the official PTCG-ABC starter schema."
        )

    # ---- Harness entrypoint ------------------------------------------------ #
    def act(self, observation: Any, configuration: Any = None):
        engine = self.decode_observation(observation, configuration)
        action = self.agent.select(engine)
        return self.encode_action(action, observation, configuration)


# Module-level singleton + function, the shape Kaggle agents usually take.
_AGENT: Optional[KaggleAgent] = None


def act(observation: Any, configuration: Any = None):
    global _AGENT
    if _AGENT is None:
        _AGENT = KaggleAgent()
    return _AGENT.act(observation, configuration)


def choose_action_on_engine(engine):
    """Convenience for local testing: pick a move directly on our engine."""
    global _AGENT
    if _AGENT is None:
        _AGENT = KaggleAgent()
    return _AGENT.agent.select(engine)
