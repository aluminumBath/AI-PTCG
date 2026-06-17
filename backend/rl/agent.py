"""RL agent: wraps a trained PolicyValueNet to play inside the engine.

Falls back gracefully: if no checkpoint exists or PyTorch is unavailable, the
caller can use the heuristic agent instead. The backend uses this to serve a
trained policy for "watch AI" and "play vs AI" modes.
"""
from __future__ import annotations

import os
from typing import Optional

import numpy as np

from engine.actions import Action
from engine.game import GameEngine
from agents.basic_agents import Agent
from . import encoder


class RLAgent(Agent):
    name = "rl"

    def __init__(self, checkpoint: Optional[str] = None, temperature: float = 0.0):
        import torch  # imported lazily so the engine works without torch
        from .network import PolicyValueNet

        self.torch = torch
        self.net = PolicyValueNet()
        self.temperature = temperature
        self.loaded = False
        if checkpoint and os.path.exists(checkpoint):
            state = torch.load(checkpoint, map_location="cpu")
            self.net.load_state_dict(state["model"])
            self.loaded = True
        self.net.eval()

    def select(self, engine: GameEngine) -> Action:
        torch = self.torch
        actions = engine.legal_actions()
        if len(actions) == 1:
            return actions[0]
        state = torch.from_numpy(encoder.encode_state(engine, engine.state.current_player))
        feats = torch.from_numpy(encoder.encode_actions(engine, actions))
        with torch.no_grad():
            logits, _ = self.net(state, feats)
            if self.temperature <= 0:
                idx = int(torch.argmax(logits).item())
            else:
                probs = torch.softmax(logits / self.temperature, dim=-1)
                idx = int(torch.multinomial(probs, 1).item())
        return actions[idx]

    def value(self, engine: GameEngine) -> float:
        torch = self.torch
        actions = engine.legal_actions()
        state = torch.from_numpy(encoder.encode_state(engine, engine.state.current_player))
        feats = torch.from_numpy(encoder.encode_actions(engine, actions or [None]))
        with torch.no_grad():
            _, v = self.net(state, feats if actions else torch.zeros((1, encoder.ACTION_DIM)))
        return float(v.item())
