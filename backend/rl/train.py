"""PPO self-play trainer.

Trains the PolicyValueNet by repeatedly playing the engine against an opponent
that is periodically refreshed to a frozen snapshot of the learner (league-style
self-play), so strategies co-evolve. Writes:
  * checkpoints  -> checkpoints/policy_latest.pt (+ periodic snapshots)
  * metrics      -> checkpoints/metrics.json   (consumed by the dashboard)

Run:
    python -m rl.train --updates 200 --episodes-per-update 16
"""
from __future__ import annotations

import argparse
import json
import os
import random
import time
from collections import deque
from typing import Callable

import numpy as np

CKPT_DIR = os.environ.get("CKPT_DIR", os.path.join(os.path.dirname(__file__), "..", "checkpoints"))
os.makedirs(CKPT_DIR, exist_ok=True)
LATEST = os.path.join(CKPT_DIR, "policy_latest.pt")
METRICS = os.path.join(CKPT_DIR, "metrics.json")


def _make_opponent(kind: str, ckpt: str | None):
    from agents.basic_agents import HeuristicAgent, RandomAgent
    if kind == "random":
        return RandomAgent().select
    if kind == "heuristic":
        return HeuristicAgent().select
    if kind == "self" and ckpt and os.path.exists(ckpt):
        from .agent import RLAgent
        return RLAgent(ckpt, temperature=0.6).select
    return HeuristicAgent().select


def train(
    updates: int = 200,
    episodes_per_update: int = 16,
    lr: float = 3e-4,
    gamma: float = 0.99,
    lam: float = 0.95,
    clip: float = 0.2,
    epochs: int = 4,
    entropy_coef: float = 0.01,
    value_coef: float = 0.5,
    opponent: str = "heuristic",
    selfplay_every: int = 25,
    seed: int = 0,
):
    import torch
    import torch.nn.functional as F
    from .network import PolicyValueNet
    from .env import SelfPlayEnv

    torch.manual_seed(seed)
    random.seed(seed)
    np.random.seed(seed)

    net = PolicyValueNet()
    if os.path.exists(LATEST):
        net.load_state_dict(torch.load(LATEST, map_location="cpu")["model"])
        print("Resumed from checkpoint.")
    opt = torch.optim.Adam(net.parameters(), lr=lr)

    env = SelfPlayEnv(opponent_policy=_make_opponent(opponent, LATEST))
    win_hist = deque(maxlen=200)
    metrics_log = []
    start = time.time()

    for update in range(1, updates + 1):
        # ---- collect rollouts ----
        batch = []  # list of episodes; each episode is list of step dicts
        wins = 0
        for ep in range(episodes_per_update):
            obs = env.reset()
            steps = []
            done = obs["done"]
            while not done:
                feats = torch.from_numpy(obs["action_feats"])
                state = torch.from_numpy(obs["state"])
                logits, value = net(state, feats)
                probs = torch.softmax(logits, dim=-1)
                dist = torch.distributions.Categorical(probs)
                a_idx = dist.sample()
                logp = dist.log_prob(a_idx)
                action = obs["actions"][int(a_idx.item())]
                next_obs, reward, done, info = env.step(action)
                steps.append({
                    "state": obs["state"],
                    "action_feats": obs["action_feats"],
                    "a_idx": int(a_idx.item()),
                    "logp": float(logp.item()),
                    "value": float(value.item()),
                    "reward": reward,
                })
                obs = next_obs
            won = info.get("winner") == env.learner_seat
            wins += int(won)
            win_hist.append(int(won))
            # ---- GAE ----
            adv, gae, next_val = [], 0.0, 0.0
            for t in reversed(range(len(steps))):
                delta = steps[t]["reward"] + gamma * next_val - steps[t]["value"]
                gae = delta + gamma * lam * gae
                adv.insert(0, gae)
                next_val = steps[t]["value"]
            for t in range(len(steps)):
                steps[t]["adv"] = adv[t]
                steps[t]["ret"] = adv[t] + steps[t]["value"]
            batch.extend(steps)

        if not batch:
            continue
        advs = np.array([s["adv"] for s in batch], dtype=np.float32)
        advs = (advs - advs.mean()) / (advs.std() + 1e-8)
        for i, s in enumerate(batch):
            s["adv_n"] = float(advs[i])

        # ---- PPO update (minibatch SGD; per-sample because action sets vary) ----
        pol_losses, val_losses, ent_terms = [], [], []
        minibatch = 32
        for _ in range(epochs):
            random.shuffle(batch)
            for mb_start in range(0, len(batch), minibatch):
                mb = batch[mb_start:mb_start + minibatch]
                opt.zero_grad()
                for s in mb:
                    state = torch.from_numpy(s["state"])
                    feats = torch.from_numpy(s["action_feats"])
                    logits, value = net(state, feats)
                    probs = torch.softmax(logits, dim=-1)
                    dist = torch.distributions.Categorical(probs)
                    logp = dist.log_prob(torch.tensor(s["a_idx"]))
                    ratio = torch.exp(logp - s["logp"])
                    adv = s["adv_n"]
                    unclipped = ratio * adv
                    clipped = torch.clamp(ratio, 1 - clip, 1 + clip) * adv
                    policy_loss = -torch.min(unclipped, clipped)
                    value_loss = F.mse_loss(value, torch.tensor(s["ret"], dtype=torch.float32))
                    entropy = dist.entropy()
                    loss = policy_loss + value_coef * value_loss - entropy_coef * entropy
                    (loss / len(mb)).backward()
                    pol_losses.append(float(policy_loss.item()))
                    val_losses.append(float(value_loss.item()))
                    ent_terms.append(float(entropy.item()))
                torch.nn.utils.clip_grad_norm_(net.parameters(), 0.5)
                opt.step()

        winrate = sum(win_hist) / len(win_hist)
        rec = {
            "update": update,
            "winrate_recent": round(winrate, 3),
            "winrate_update": round(wins / episodes_per_update, 3),
            "policy_loss": round(float(np.mean(pol_losses)), 4),
            "value_loss": round(float(np.mean(val_losses)), 4),
            "entropy": round(float(np.mean(ent_terms)), 4),
            "episodes": update * episodes_per_update,
            "elapsed_s": round(time.time() - start, 1),
            "opponent": opponent,
        }
        metrics_log.append(rec)
        torch.save({"model": net.state_dict()}, LATEST)
        with open(METRICS, "w") as fh:
            json.dump(metrics_log, fh, indent=2)
        print(
            f"upd {update:3d} | winrate {winrate:.2f} | "
            f"ploss {rec['policy_loss']:.3f} vloss {rec['value_loss']:.3f} "
            f"ent {rec['entropy']:.2f} | {rec['elapsed_s']}s"
        )

        # league self-play: promote learner to opponent periodically
        if opponent == "self" or (selfplay_every and update % selfplay_every == 0):
            snap = os.path.join(CKPT_DIR, f"policy_snapshot_{update}.pt")
            torch.save({"model": net.state_dict()}, snap)
            env.set_opponent(_make_opponent("self", LATEST))

    print(f"Done. Latest checkpoint: {LATEST}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--updates", type=int, default=200)
    ap.add_argument("--episodes-per-update", type=int, default=16)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--opponent", choices=["random", "heuristic", "self"], default="heuristic")
    ap.add_argument("--selfplay-every", type=int, default=25)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    train(
        updates=args.updates,
        episodes_per_update=args.episodes_per_update,
        lr=args.lr,
        opponent=args.opponent,
        selfplay_every=args.selfplay_every,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
