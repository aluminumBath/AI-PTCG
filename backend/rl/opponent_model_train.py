"""Train the neural opponent model.

Plays engine self-play, and at each decision point records, for the *opponent's*
actually-remaining cards, whether each is currently in their hand — labelled
because the engine knows the true state. Features = [public-state (mover
perspective), card features]. Trains a binary classifier (in-hand vs not) used by
``agents.neural_ismcts_agent`` to weight ISMCTS determinizations.

This is an **offline training tool**, not part of any competition submission.

Run:
    python -m rl.opponent_model_train --games 300 --epochs 4 --device mps
"""
from __future__ import annotations

import argparse
import json
import os
import random
import time

import numpy as np

CKPT_DIR = os.environ.get("CKPT_DIR", os.path.join(os.path.dirname(__file__), "..", "checkpoints"))
OUT = os.path.join(CKPT_DIR, "opponent_model.pt")


def _pick_device(name: str):
    import torch
    if name == "auto":
        if torch.backends.mps.is_available():
            return "mps"
        if torch.cuda.is_available():
            return "cuda"
        return "cpu"
    return name


def collect(games: int, max_moves: int, neg_per_pos: int, rng: random.Random):
    from agents.basic_agents import HeuristicAgent
    from agents.opponent_model import assemble_rows
    from engine.game import GameEngine
    from data.cards_db import DECKS

    deck_ids = list(DECKS.keys())
    hero = HeuristicAgent(rng)
    X, y = [], []
    for _ in range(games):
        a, b = rng.sample(deck_ids, 2)
        eng = GameEngine.new_game(DECKS[a](), DECKS[b](), names=(a, b),
                                  seed=rng.randint(0, 2**31 - 1))
        moves = 0
        while not eng.state.is_over() and moves < max_moves:
            cur = eng.state.current_player
            opp = eng.state.players[1 - cur]
            pool = list(opp.hand) + list(opp.deck) + list(opp.prizes)
            nh = len(opp.hand)
            if nh and len(pool) > nh:
                rows = assemble_rows(eng, cur, pool)        # (N, INPUT_DIM)
                neg_idx = rng.sample(range(nh, len(pool)),
                                     min(len(pool) - nh, neg_per_pos * nh))
                for i in range(nh):
                    X.append(rows[i]); y.append(1.0)        # hand = positive
                for i in neg_idx:
                    X.append(rows[i]); y.append(0.0)        # deck/prize = negative
            eng.apply(hero.select(eng))
            moves += 1
    return np.asarray(X, dtype=np.float32), np.asarray(y, dtype=np.float32)


def train(games=300, epochs=4, lr=1e-3, batch=256, device="auto", out=OUT,
          max_moves=80, neg_per_pos=1, seed=0, metrics_path=None):
    import torch
    import torch.nn as nn
    from agents.opponent_model import build_net, CARD_DIM, INPUT_DIM
    from rl.encoder import STATE_DIM

    dev = _pick_device(device)
    torch.manual_seed(seed); random.seed(seed); np.random.seed(seed)
    rng = random.Random(seed)

    print(f"Collecting self-play data from {games} games…")
    X, y = collect(games, max_moves, neg_per_pos, rng)
    if len(X) < 50:
        print(f"Only {len(X)} samples collected; need more games."); return
    pos = float(y.mean())
    print(f"{len(X)} samples ({pos:.0%} in-hand), dim {X.shape[1]} (= {INPUT_DIM}: state {STATE_DIM} + card {CARD_DIM} + pool 8)")

    net = build_net().to(dev)
    opt = torch.optim.Adam(net.parameters(), lr=lr, weight_decay=1e-5)
    lossf = nn.BCEWithLogitsLoss()

    Xt = torch.from_numpy(X); yt = torch.from_numpy(y)
    n = len(X)
    idx = np.arange(n); np.random.shuffle(idx)
    nval = max(1, int(0.15 * n))
    val_idx, tr_idx = idx[:nval], idx[nval:]
    yv = y[val_idx]
    out_dir = os.path.dirname(out) or "."
    os.makedirs(out_dir, exist_ok=True)
    metrics_path = metrics_path or os.path.join(out_dir, "opponent_metrics.json")
    log, start = [], time.time()

    def _stats(rows, labels):
        with torch.no_grad():
            p = torch.sigmoid(net(Xt[rows].to(dev)).squeeze(-1)).cpu().numpy()
        acc = float(((p >= 0.5).astype(np.float32) == labels).mean())
        return acc, float(p[labels == 1].mean()), float(p[labels == 0].mean())

    for ep in range(1, epochs + 1):
        np.random.shuffle(tr_idx)
        losses = []
        net.train()
        for s in range(0, len(tr_idx), batch):
            j = tr_idx[s:s + batch]
            xb = Xt[j].to(dev); yb = yt[j].to(dev)
            opt.zero_grad()
            loss = lossf(net(xb).squeeze(-1), yb)
            loss.backward(); opt.step()
            losses.append(float(loss.item()))
        net.eval()
        tr_acc, tr_in, tr_out = _stats(tr_idx, y[tr_idx])
        val_acc, val_in, val_out = _stats(val_idx, yv)        # held-out — the honest signal
        rec = {"epoch": ep, "loss": round(float(np.mean(losses)), 4),
               "acc": round(tr_acc, 3), "p_inhand": round(tr_in, 3), "p_other": round(tr_out, 3),
               "val_acc": round(val_acc, 3), "val_p_inhand": round(val_in, 3), "val_p_other": round(val_out, 3),
               "samples": n, "val_samples": int(nval), "elapsed_s": round(time.time() - start, 1)}
        log.append(rec)
        torch.save({"model": net.state_dict(), "input_dim": INPUT_DIM,
                    "card_dim": CARD_DIM, "state_dim": STATE_DIM}, out)
        json.dump(log, open(metrics_path, "w"), indent=2)
        print(f"epoch {ep}/{epochs} | loss {rec['loss']} | acc {rec['acc']} (val {rec['val_acc']}) | "
              f"val P(in-hand) {val_in:.2f} vs other {val_out:.2f} (Δ{val_in - val_out:+.2f}) | {rec['elapsed_s']}s")
    print(f"Done. Opponent model: {out}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=300)
    ap.add_argument("--epochs", type=int, default=4)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--batch", type=int, default=256)
    ap.add_argument("--device", type=str, default="auto", help="auto|cpu|mps|cuda")
    ap.add_argument("--out", type=str, default=OUT)
    ap.add_argument("--max-moves", type=int, default=80)
    ap.add_argument("--neg-per-pos", type=int, default=1, help="negatives sampled per in-hand card")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--metrics", type=str, default=None)
    a = ap.parse_args()
    train(games=a.games, epochs=a.epochs, lr=a.lr, batch=a.batch, device=a.device, out=a.out,
          max_moves=a.max_moves, neg_per_pos=a.neg_per_pos, seed=a.seed, metrics_path=a.metrics)


if __name__ == "__main__":
    main()
