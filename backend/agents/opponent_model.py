"""Neural opponent model — a learned, pool-aware "deep mind-reader".

Predicts, from the observer's public view, how likely each of the opponent's
*actually-remaining* cards is to be **in their hand right now** (versus buried in
deck/prizes). ISMCTS uses these scores to weight its determinizations toward the
hidden states the model finds plausible, instead of sampling the opponent's
hand/deck/prize split uniformly (see ``agents.neural_ismcts_agent``).

Features per card = [public-state (observer perspective), card features,
**pool-context**]. The pool-context conditions the prediction on the *actual
cards in play this game* — the opponent's remaining hand/deck/prize sizes, the
turn, the Pokémon/Trainer/Energy mix of their remaining pool, and how many copies
of this very card are left — so the same model behaves differently for an
energy-flooded deck vs a trainer-heavy one, and adapts to imported/custom decks.

Trained as a binary classifier (in-hand vs not) on engine self-play, where the
true hand is known — see ``rl/opponent_model_train.py``. Faithful at play time:
it conditions only on the observer's public information plus the opponent's known
card pool (the same pool plain ISMCTS already re-partitions), never on the true
hand/deck split.
"""
from __future__ import annotations

import os
from collections import Counter
from typing import List, Optional

import numpy as np

from engine.cards import CardDef
from engine.enums import CardCategory, Stage, TrainerKind
from rl.encoder import STATE_DIM, encode_state

CARD_DIM = 19      # encode_card
POOL_DIM = 8       # encode_pool_context (7) + per-card copies-remaining (1)
INPUT_DIM = STATE_DIM + CARD_DIM + POOL_DIM


def encode_card(card: CardDef) -> np.ndarray:
    """Compact, hand-relevant features of a card definition."""
    cat = [
        1.0 if card.category == CardCategory.POKEMON else 0.0,
        1.0 if card.category == CardCategory.TRAINER else 0.0,
        1.0 if card.category == CardCategory.ENERGY else 0.0,
    ]
    tk = getattr(card, "trainer_kind", None)
    tkv = [
        1.0 if tk == TrainerKind.ITEM else 0.0,
        1.0 if tk == TrainerKind.SUPPORTER else 0.0,
        1.0 if tk == TrainerKind.STADIUM else 0.0,
        1.0 if tk == TrainerKind.TOOL else 0.0,
        1.0 if tk is None else 0.0,
    ]
    st = getattr(card, "stage", None)
    stv = [
        1.0 if st == Stage.BASIC else 0.0,
        1.0 if st == Stage.STAGE_1 else 0.0,
        1.0 if st == Stage.STAGE_2 else 0.0,
        1.0 if st is None else 0.0,
    ]
    attacks = getattr(card, "attacks", ()) or ()
    max_dmg = max((a.damage for a in attacks), default=0)
    scalars = [
        (getattr(card, "hp", 0) or 0) / 340.0,
        (getattr(card, "retreat_cost", 0) or 0) / 4.0,
        len(attacks) / 3.0,
        max_dmg / 340.0,
        1.0 if getattr(card, "abilities", ()) else 0.0,
        1.0 if getattr(card, "rule_box", None) else 0.0,
        1.0 if getattr(card, "is_basic_energy", False) else 0.0,
    ]
    return np.asarray(cat + tkv + stv + scalars, dtype=np.float32)


def encode_pool_context(engine, observer: int) -> np.ndarray:
    """Game-specific context about the opponent's *remaining* card pool."""
    opp = engine.state.players[1 - observer]
    pool = list(opp.hand) + list(opp.deck) + list(opp.prizes)
    n = max(1, len(pool))
    pk = sum(1 for ci in pool if ci.card.category == CardCategory.POKEMON)
    tr = sum(1 for ci in pool if ci.card.category == CardCategory.TRAINER)
    en = sum(1 for ci in pool if ci.card.category == CardCategory.ENERGY)
    turn = getattr(engine.state, "turn_number", 0) or 0
    return np.asarray([
        len(opp.hand) / 10.0,
        len(opp.deck) / 60.0,
        len(opp.prizes) / 6.0,
        turn / 30.0,
        pk / n, tr / n, en / n,
    ], dtype=np.float32)


def assemble_rows(engine, observer: int, pool: List) -> np.ndarray:
    """Feature matrix (len(pool), INPUT_DIM) for the given pool of CardInstances.
    Shared by training and inference so they are guaranteed identical."""
    state = encode_state(engine, observer)
    ctx = encode_pool_context(engine, observer)
    counts = Counter(ci.card.name for ci in pool)
    rows = []
    for ci in pool:
        copies = min(counts[ci.card.name], 4) / 4.0
        rows.append(np.concatenate([state, encode_card(ci.card), ctx, [copies]]))
    return np.stack(rows).astype(np.float32)


def build_net(hidden: int = 128):
    import torch.nn as nn
    return nn.Sequential(
        nn.Linear(INPUT_DIM, hidden), nn.ReLU(),
        nn.Linear(hidden, hidden), nn.ReLU(),
        nn.Linear(hidden, 1),
    )


class OpponentModel:
    """Loads a trained net and scores a pool of cards by P(in opponent hand)."""

    def __init__(self, checkpoint: Optional[str] = None):
        import torch
        self.torch = torch
        self.net = build_net()
        self.loaded = False
        if checkpoint and os.path.exists(checkpoint):
            state = torch.load(checkpoint, map_location="cpu")
            # only load if the architecture matches (input dim may have changed)
            if state.get("input_dim", INPUT_DIM) == INPUT_DIM:
                try:
                    self.net.load_state_dict(state["model"])
                    self.loaded = True
                except Exception:
                    self.loaded = False
        self.net.eval()

    def score_cards(self, engine, observer: int, pool: List) -> np.ndarray:
        """Return P(in hand) in [0,1] for each CardInstance in ``pool``."""
        if not pool:
            return np.zeros(0, dtype=np.float64)
        torch = self.torch
        x = assemble_rows(engine, observer, pool)
        with torch.no_grad():
            logits = self.net(torch.from_numpy(x)).squeeze(-1)
            return torch.sigmoid(logits).cpu().numpy().astype(np.float64)
