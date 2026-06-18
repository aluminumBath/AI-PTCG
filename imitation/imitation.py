"""Behavioural cloning from human games.

The policy is a softmax over each legal action's features, so imitating a human
is simply: for each recorded decision (state, legal-action features, the index
the winner chose), push probability mass onto that index. This lets the RL
agents learn the strategy that won a multiplayer game.

Checkpoints use the same `{"model": state_dict}` format as the PPO trainer, so a
cloned/finetuned policy drops straight into the `rl` and `rl_mcts` agents.
"""
from __future__ import annotations

import json
import os
from typing import Callable, Optional


def load_dataset(path: str) -> list[dict]:
    samples: list[dict] = []
    if not path or not os.path.exists(path):
        return samples
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            if d.get("action_feats") and isinstance(d.get("chosen_index"), int):
                samples.append(d)
    return samples


def behavioral_clone(net, samples: list[dict], epochs: int = 5, lr: float = 1e-3,
                     batch: int = 16, log: Optional[Callable[[dict], None]] = None) -> list[dict]:
    import numpy as np
    import torch

    opt = torch.optim.Adam(net.parameters(), lr=lr)
    ce = torch.nn.CrossEntropyLoss()
    history: list[dict] = []
    net.train()
    for ep in range(epochs):
        order = list(range(len(samples)))
        np.random.shuffle(order)
        losses: list[float] = []
        correct = total = 0
        opt.zero_grad()
        acc = None
        n_in_batch = 0
        for j in order:
            s = samples[j]
            feats = torch.tensor(s["action_feats"], dtype=torch.float32)
            if feats.dim() != 2 or feats.shape[0] < 2:
                continue  # no real choice to learn from
            idx = int(s["chosen_index"])
            if idx < 0 or idx >= feats.shape[0]:
                continue
            state = torch.tensor(s["state"], dtype=torch.float32)
            logits, _ = net(state, feats)              # (A,)
            loss = ce(logits.unsqueeze(0), torch.tensor([idx]))
            acc = loss if acc is None else acc + loss
            n_in_batch += 1
            losses.append(float(loss.item()))
            if int(torch.argmax(logits).item()) == idx:
                correct += 1
            total += 1
            if n_in_batch >= batch:
                (acc / n_in_batch).backward()
                opt.step(); opt.zero_grad()
                acc = None; n_in_batch = 0
        if n_in_batch > 0 and acc is not None:
            (acc / n_in_batch).backward()
            opt.step(); opt.zero_grad()
        rec = {"epoch": ep + 1,
               "loss": round(float(np.mean(losses)), 4) if losses else None,
               "accuracy": round(correct / total, 3) if total else 0.0,
               "samples": total}
        history.append(rec)
        if log:
            log(rec)
    net.eval()
    return history


def clone_from_file(dataset_path: str, checkpoint_in: Optional[str],
                    checkpoint_out: str, epochs: int = 5, lr: float = 1e-3,
                    min_samples: int = 10,
                    log: Optional[Callable[[dict], None]] = None) -> dict:
    import torch
    from rl.network import PolicyValueNet

    samples = load_dataset(dataset_path)
    usable = [s for s in samples if len(s.get("action_feats", [])) >= 2]
    if len(usable) < min_samples:
        raise ValueError(
            f"need at least {min_samples} decision samples to learn, have {len(usable)}")

    net = PolicyValueNet()
    if checkpoint_in and os.path.exists(checkpoint_in):
        try:
            net.load_state_dict(torch.load(checkpoint_in, map_location="cpu")["model"])
        except Exception:
            pass  # start fresh if the existing checkpoint can't be read

    history = behavioral_clone(net, usable, epochs=epochs, lr=lr, log=log)
    os.makedirs(os.path.dirname(checkpoint_out) or ".", exist_ok=True)
    torch.save({"model": net.state_dict()}, checkpoint_out)
    return {"history": history, "samples": len(usable), "out": checkpoint_out}
