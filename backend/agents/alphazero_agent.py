"""AlphaZero-style PUCT search.

A best-first tree search guided by a policy + value evaluator: the policy supplies
action priors and the value estimates leaves (no random rollouts). Selection uses

    a* = argmax_a  Q(s,a) + c_puct * P(s,a) * sqrt(SumN) / (1 + N(s,a))

Values are tracked from each node's *mover* perspective -- this engine's turns are
not strictly alternating (a player takes several actions before ending the turn),
so we flip by who is to move, not by ply parity.

``run_puct`` is shared by the playing agent (``AlphaZeroAgent``) and the self-play
trainer (``rl/alphazero_train.py``), so search and training use identical code.
The evaluator has signature::

    evaluate(engine, to_move) -> (actions, priors[np], value_in_to_move_perspective)
"""
from __future__ import annotations

import math
import os
import random
import time
from typing import Callable, Optional

import numpy as np

from engine.actions import Action
from engine.game import GameEngine
from agents.basic_agents import Agent
from .closer_agent import find_lethal, lethal_plausible

Evaluator = Callable[[GameEngine, int], "tuple[list, np.ndarray, float]"]


class _PNode:
    __slots__ = ("engine", "to_move", "terminal", "actions", "P", "N", "W", "v_self", "children")

    def __init__(self, engine: GameEngine):
        self.engine = engine
        self.to_move = engine.state.current_player
        self.terminal = engine.state.is_over()
        self.actions = None
        self.P = None
        self.N = None
        self.W = None
        self.v_self = 0.0
        self.children = {}


def _expand(node: _PNode, evaluate: Evaluator) -> None:
    actions, priors, value = evaluate(node.engine, node.to_move)
    node.actions = actions
    node.P = np.asarray(priors, dtype=np.float64)
    node.v_self = float(value)              # this node's mover perspective
    node.N = np.zeros(len(actions), dtype=np.float64)
    node.W = np.zeros(len(actions), dtype=np.float64)


def _puct_action(node: _PNode, root_player: int, c_puct: float) -> int:
    sqrt_total = math.sqrt(max(1.0, float(node.N.sum())))
    q_root = np.divide(node.W, node.N, out=np.zeros_like(node.W), where=node.N > 0)
    sign = 1.0 if node.to_move == root_player else -1.0   # to this node's perspective
    scores = sign * q_root + c_puct * node.P * sqrt_total / (1.0 + node.N)
    return int(scores.argmax())


def _simulate(root: _PNode, root_player: int, evaluate: Evaluator, c_puct: float) -> None:
    node = root
    path = []
    while True:
        if node.terminal:
            w = node.engine.state.winner
            value_ref = 0.0 if w is None else (1.0 if w == root_player else -1.0)
            break
        if node.actions is None:
            _expand(node, evaluate)
            value_ref = node.v_self if node.to_move == root_player else -node.v_self
            break
        a = _puct_action(node, root_player, c_puct)
        path.append((node, a))
        child = node.children.get(a)
        if child is None:
            ce = node.engine.clone()
            try:
                ce.apply(node.actions[a])
            except Exception:
                ce = node.engine.clone()       # defensive; treat as no-op
            child = _PNode(ce)
            node.children[a] = child
        node = child
    for n, a in path:
        n.N[a] += 1.0
        n.W[a] += value_ref


def run_puct(engine: GameEngine, evaluate: Evaluator, iterations: int,
             c_puct: float = 1.5, rng: Optional[random.Random] = None,
             root_noise: float = 0.0, dir_alpha: float = 0.3,
             max_seconds: float = 0.0) -> _PNode:
    """Run PUCT from ``engine`` and return the expanded root node.

    ``root_noise`` (>0) mixes Dirichlet(``dir_alpha``) noise into the root priors
    for self-play exploration; leave 0 for strongest play. ``max_seconds`` (>0)
    caps wall-clock time per move — a safety valve for the competition's match
    time limit when this agent is used in a submission.
    """
    root = _PNode(engine.clone())
    _expand(root, evaluate)
    if root_noise > 0.0 and len(root.P) > 1:
        rs = np.random.RandomState(rng.randint(0, 2**31 - 1) if rng else None)
        noise = rs.dirichlet([dir_alpha] * len(root.P))
        root.P = (1.0 - root_noise) * root.P + root_noise * noise
    root_player = root.to_move
    deadline = (time.monotonic() + max_seconds) if max_seconds > 0 else None
    for i in range(iterations):
        _simulate(root, root_player, evaluate, c_puct)
        if deadline is not None and (i & 15) == 0 and time.monotonic() > deadline:
            break
    return root


class AlphaZeroAgent(Agent):
    name = "alphazero"

    def __init__(self, checkpoint: Optional[str] = None, iterations: int = 300,
                 c_puct: float = 1.5, use_closer: bool = True,
                 max_seconds: float = 0.0,
                 rng: Optional[random.Random] = None):
        import torch
        from rl.agent import RLAgent
        self.torch = torch
        self.iterations = iterations
        self.c_puct = c_puct
        self.use_closer = use_closer
        # Per-move time cap (seconds); env PTCG_MOVE_BUDGET overrides. 0 = unlimited.
        self.max_seconds = float(os.environ.get("PTCG_MOVE_BUDGET", max_seconds) or 0.0)
        self.rng = rng or random.Random()
        self._rl = RLAgent(checkpoint, temperature=0.0)   # raises w/o torch/ckpt
        self.last_explanation = ""

    def _evaluate(self, engine: GameEngine, to_move: int):
        from rl import encoder
        torch = self.torch
        actions = engine.legal_actions()
        state = torch.from_numpy(encoder.encode_state(engine, to_move))
        feats = torch.from_numpy(encoder.encode_actions(engine, actions))
        with torch.no_grad():
            logits, value = self._rl.net(state, feats)
            priors = torch.softmax(logits, dim=-1).cpu().numpy().astype(np.float64)
            v = math.tanh(float(value.item()))
        return actions, priors, v

    def select(self, engine: GameEngine) -> Action:
        actions = engine.legal_actions()
        if len(actions) == 1:
            return actions[0]
        me = engine.state.current_player

        if self.use_closer and lethal_plausible(engine, me):
            line = find_lethal(engine, me)
            if line:
                self.last_explanation = f"AlphaZero: forced lethal in {len(line)} step(s)."
                return line[0]

        root = run_puct(engine, self._evaluate, self.iterations, self.c_puct, self.rng,
                        max_seconds=self.max_seconds)
        best = int(root.N.argmax())
        visits = int(root.N[best])
        q = float(root.W[best] / max(1.0, root.N[best]))
        self.last_explanation = (
            f"AlphaZero PUCT: {self.iterations} sims -> '{root.actions[best].type.value}' "
            f"(visits {visits}, Q {q:+.2f})."
        )
        return root.actions[best]
