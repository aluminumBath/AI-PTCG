"""Policy + value network.

Architecture (pointer / action-scoring):
  state  --MLP-->  h  (state embedding)
  for each legal action feature a_i:  logit_i = MLP([h, a_i])
  policy = softmax(logits over legal actions)
  value  = MLP(h)  -> scalar V(s)

This cleanly handles the variable, state-dependent action sets of a TCG without
a fixed global action index. Requires PyTorch (install with the training extra).
"""
from __future__ import annotations

import torch
import torch.nn as nn

from .encoder import ACTION_DIM, STATE_DIM


class PolicyValueNet(nn.Module):
    def __init__(self, hidden: int = 256):
        super().__init__()
        self.state_encoder = nn.Sequential(
            nn.Linear(STATE_DIM, hidden), nn.ReLU(),
            nn.Linear(hidden, hidden), nn.ReLU(),
        )
        self.action_scorer = nn.Sequential(
            nn.Linear(hidden + ACTION_DIM, hidden), nn.ReLU(),
            nn.Linear(hidden, 1),
        )
        self.value_head = nn.Sequential(
            nn.Linear(hidden, hidden // 2), nn.ReLU(),
            nn.Linear(hidden // 2, 1),
        )

    def forward(
        self, state: torch.Tensor, action_feats: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """state: (S,)  action_feats: (A, ACTION_DIM)
        returns logits: (A,) and value: scalar."""
        h = self.state_encoder(state)                 # (H,)
        a = action_feats.shape[0]
        h_rep = h.unsqueeze(0).expand(a, -1)           # (A, H)
        scorer_in = torch.cat([h_rep, action_feats], dim=-1)
        logits = self.action_scorer(scorer_in).squeeze(-1)  # (A,)
        value = self.value_head(h).squeeze(-1)         # scalar
        return logits, value
