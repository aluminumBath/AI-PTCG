"""ISMCTS guided by a neural opponent model.

Standard ISMCTS samples the opponent's hidden hand/deck/prize split uniformly.
This variant **weights** that split by a learned opponent model
(``agents.opponent_model``): the opponent's actually-remaining cards are dealt
into the hand in proportion to the model's predicted P(in hand), so the search
spends its determinizations on the hidden states the model finds plausible.

Falls back to uniform determinization (i.e. plain ISMCTS) when no trained model
or PyTorch is available, so it always plays.
"""
from __future__ import annotations

import math
import random
from typing import Optional

import numpy as np

from engine.game import GameEngine
from .ismcts_agent import ISMCTSAgent, determinize


def _gumbel_topk(weights: np.ndarray, k: int, rng: random.Random) -> set:
    """Indices of a size-``k`` sample drawn without replacement ∝ ``weights``."""
    n = len(weights)
    if k <= 0:
        return set()
    if k >= n:
        return set(range(n))
    logw = np.log(np.clip(weights, 1e-9, None))
    g = np.array([-math.log(-math.log(rng.random())) for _ in range(n)])
    return set(int(i) for i in np.argsort(-(logw + g))[:k])


def determinize_weighted(engine: GameEngine, observer: int, model, rng: random.Random) -> GameEngine:
    """Like ``determinize`` but biases the opponent's hand by the model's scores."""
    sim = engine.clone()
    me = sim.state.players[observer]
    pool = list(me.deck) + list(me.prizes)          # our own hand is known; deck/prizes hidden
    rng.shuffle(pool)
    npz = len(me.prizes)
    me.prizes = pool[:npz]; me.deck = pool[npz:]

    opp = sim.state.players[1 - observer]
    pool = list(opp.hand) + list(opp.deck) + list(opp.prizes)
    nh, npz = len(opp.hand), len(opp.prizes)
    if not pool:
        return sim
    scores = model.score_cards(engine, observer, pool) + 1e-6   # P(in hand)
    hand_idx = _gumbel_topk(scores, nh, rng)
    hand = [pool[i] for i in range(len(pool)) if i in hand_idx]
    rest = [pool[i] for i in range(len(pool)) if i not in hand_idx]
    rng.shuffle(rest)
    opp.hand = hand
    opp.prizes = rest[:npz]
    opp.deck = rest[npz:]
    return sim


class NeuralISMCTSAgent(ISMCTSAgent):
    name = "neural_ismcts"

    def __init__(self, model_checkpoint: Optional[str] = None, iterations: int = 160, **kw):
        super().__init__(iterations=iterations, **kw)
        from .opponent_model import OpponentModel
        self._model = OpponentModel(model_checkpoint)   # raises if torch missing
        self.last_explanation = ""
        self.last_hand_read = []      # top cards the model thinks the opponent holds
        self.last_read_eval = None    # accuracy of that prediction vs the true hand

    def _determinize(self, engine: GameEngine, observer: int) -> GameEngine:
        if getattr(self, "_model", None) and self._model.loaded:
            return determinize_weighted(engine, observer, self._model, self.rng)
        return determinize(engine, observer, self.rng)

    def _eval_read(self, engine: GameEngine):
        """Score the opponent's pool once; return (top predicted hand cards,
        accuracy of that prediction vs the *true* hand the engine knows)."""
        me = engine.state.current_player
        opp = engine.state.players[1 - me]
        hand = list(opp.hand)
        pool = hand + list(opp.deck) + list(opp.prizes)   # indices [0,nh) are the true hand
        nh = len(hand)
        if not pool:
            return [], None
        scores = self._model.score_cards(engine, me, pool)
        best: dict = {}
        for ci, p in zip(pool, scores):
            nm = ci.card.name
            if nm not in best or p > best[nm]:
                best[nm] = float(p)
        hand_read = sorted(({"name": n, "prob": round(p, 3)} for n, p in best.items()),
                           key=lambda d: d["prob"], reverse=True)[:6]
        read_eval = None
        if nh and len(pool) > nh:
            topk = set(int(i) for i in np.argsort(-scores)[:nh])   # model's nh most-likely
            hits = sum(1 for i in topk if i < nh)                  # how many are truly in hand
            read_eval = {"hand_size": nh, "hits": hits,
                         "precision_at_hand": round(hits / nh, 3),
                         "p_in": round(float(scores[:nh].mean()), 3),
                         "p_out": round(float(scores[nh:].mean()), 3)}
        return hand_read, read_eval

    def select(self, engine: GameEngine):
        action = super().select(engine)
        if self._model and self._model.loaded:
            self.last_explanation = ("ISMCTS + neural opponent model: determinizations weighted "
                                     "by predicted opponent hand.")
            try:
                self.last_hand_read, self.last_read_eval = self._eval_read(engine)
            except Exception:
                self.last_hand_read, self.last_read_eval = [], None
        else:
            self.last_explanation = "ISMCTS (uniform determinization — no opponent model loaded)."
            self.last_hand_read, self.last_read_eval = [], None
        return action
