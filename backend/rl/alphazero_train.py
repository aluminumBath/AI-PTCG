"""AlphaZero self-play trainer — with resume/scheduler and an optional league.

Generates games by self-play guided by the **same PUCT search the agent uses**
(`agents.alphazero_agent.run_puct`), recording at every learner move the state +
legal-action features, the search's **visit-count distribution** as the policy
target (pi = N / sum N), and (after the game) the outcome z in {-1,0,+1} from
that mover's perspective. It then trains the policy/value net to match pi
(cross-entropy) and z (MSE on tanh(value)). Repeat: better net -> stronger
search -> better targets -> better net.

Resume / scheduler
------------------
A run-state sidecar (``<out_dir>/az_run.json``) records iterations completed so
re-invoking the same command **continues toward the target ``--iters``** rather
than restarting (``--resume``). Across the run the learning rate decays on a
cosine schedule and exploration (Dirichlet noise, sampling temperature) anneals.

League / exploiters (``--league``)
----------------------------------
Instead of pure mirror self-play, the learner plays a pool of frozen opponents
(the heuristic, optional ISMCTS, and periodic snapshots of the learner). Opponents
are sampled with priority toward those that **beat the learner** (AlphaStar-style
exploiters), and only the *learner's* moves are recorded — so the policy targets
stay clean while the data covers tougher, more varied opponents.

These are **offline training tools**; they are not part of any competition
submission (see COMPLIANCE.md).

Run (quick smoke):       python -m rl.alphazero_train --iters 2 --games 4 --sims 32
Real (Mac GPU, resumable):
    python -m rl.alphazero_train --iters 200 --games 30 --sims 160 --device mps \
        --league --league-add-every 10 --eval-games 20 --resume
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import time
from collections import deque

import numpy as np

CKPT_DIR = os.environ.get("CKPT_DIR", os.path.join(os.path.dirname(__file__), "..", "checkpoints"))
LATEST = os.path.join(CKPT_DIR, "policy_latest.pt")


def _pick_device(name: str):
    import torch
    if name == "auto":
        if torch.backends.mps.is_available():
            return "mps"
        if torch.cuda.is_available():
            return "cuda"
        return "cpu"
    return name


def _outcome(mover: int, winner) -> float:
    if winner is None:
        return 0.0
    return 1.0 if winner == mover else -1.0


class _League:
    """Pool of frozen opponents with prioritized 'exploiter' sampling."""

    def __init__(self, dev, opponent_sims, include_ismcts, rng):
        from agents.basic_agents import HeuristicAgent
        self.dev = dev
        self.opponent_sims = opponent_sims
        self.rng = rng
        self.members = []
        self.add_agent("heuristic", HeuristicAgent(rng))
        if include_ismcts:
            from agents.ismcts_agent import ISMCTSAgent
            self.add_agent("ismcts", ISMCTSAgent(iterations=200))

    def add_agent(self, mid, agent):
        self.members.append({"id": mid, "kind": "agent", "agent": agent, "w": 0, "g": 0})

    def add_net(self, mid, state_dict, size_cap):
        from .network import PolicyValueNet
        net = PolicyValueNet().to(self.dev)
        net.load_state_dict(state_dict)
        net.eval()
        self.members.append({"id": mid, "kind": "net", "net": net, "w": 0, "g": 0})
        nets = [m for m in self.members if m["kind"] == "net"]
        if len(nets) > size_cap:                       # drop the oldest snapshot
            self.members.remove(nets[0])

    def _eval(self, net):
        import torch
        from . import encoder
        def evaluate(engine, to_move):
            actions = engine.legal_actions()
            state = torch.from_numpy(encoder.encode_state(engine, to_move)).to(self.dev)
            feats = torch.from_numpy(encoder.encode_actions(engine, actions)).to(self.dev)
            with torch.no_grad():
                logits, value = net(state, feats)
                priors = torch.softmax(logits, dim=-1).cpu().numpy().astype(np.float64)
                v = float(torch.tanh(value).item())
            return actions, priors, v
        return evaluate

    def sample(self):
        # weight by beat-rate vs the learner (favour opponents that win), with a
        # floor so every member keeps some probability.
        weights = [0.15 + (m["w"] / m["g"] if m["g"] else 0.5) for m in self.members]
        total = sum(weights)
        r = self.rng.random() * total
        acc = 0.0
        for m, w in zip(self.members, weights):
            acc += w
            if r <= acc:
                return m
        return self.members[-1]

    def move(self, m, engine):
        from agents.alphazero_agent import run_puct
        if m["kind"] == "agent":
            return m["agent"].select(engine)
        net = m["net"]
        if self.opponent_sims > 0:
            root = run_puct(engine, self._eval(net), self.opponent_sims, 1.5, self.rng)
            return root.actions[int(root.N.argmax())]
        import torch
        from . import encoder
        actions = engine.legal_actions()
        state = torch.from_numpy(encoder.encode_state(engine, engine.state.current_player)).to(self.dev)
        feats = torch.from_numpy(encoder.encode_actions(engine, actions)).to(self.dev)
        with torch.no_grad():
            logits, _ = net(state, feats)
            idx = int(logits.argmax().item())
        return actions[idx]

    def record(self, m, opp_won: bool):
        m["g"] += 1
        m["w"] += int(opp_won)

    def summary(self):
        return ", ".join(f"{m['id']}:{(m['w']/m['g'] if m['g'] else 0):.0%}" for m in self.members)

    def standings(self):
        return [{"id": m["id"], "kind": m["kind"], "games": m["g"], "wins_vs_learner": m["w"],
                 "beat_rate": round(m["w"] / m["g"], 3) if m["g"] else None}
                for m in self.members]


def train(iters=10, games=20, sims=160, c_puct=1.5, max_moves=120, temp_moves=12,
          dirichlet=0.25, lr=1e-3, value_coef=1.0, weight_decay=1e-4, epochs=2,
          batch=32, buffer_size=20000, out=LATEST, warm_start=LATEST, scratch=False,
          device="auto", seed=0, eval_games=0, snapshot_every=0, metrics_path=None,
          resume=False, lr_final_frac=0.1, dir_final_frac=0.2,
          league=False, league_add_every=10, league_size=6, opponent_sims=0,
          league_ismcts=False):
    import torch
    import torch.nn.functional as F
    from .network import PolicyValueNet
    from . import encoder
    from agents.alphazero_agent import run_puct
    from engine.game import GameEngine
    from data.cards_db import DECKS

    dev = _pick_device(device)
    torch.manual_seed(seed); random.seed(seed); np.random.seed(seed)
    rng = random.Random(seed)
    deck_ids = list(DECKS.keys())

    out_dir = os.path.dirname(out) or "."
    os.makedirs(out_dir, exist_ok=True)
    metrics_path = metrics_path or os.path.join(out_dir, "metrics.json")
    run_state_path = os.path.join(out_dir, "az_run.json")

    # ---- resume bookkeeping ------------------------------------------------ #
    start_iter = 0
    if resume and os.path.exists(run_state_path):
        try:
            st = json.load(open(run_state_path))
            start_iter = int(st.get("iters_done", 0))
            print(f"Resuming: {start_iter}/{iters} iterations already done.")
        except Exception:
            start_iter = 0

    net = PolicyValueNet().to(dev)
    load_from = out if (resume and os.path.exists(out)) else warm_start
    if not scratch and load_from and os.path.exists(load_from):
        net.load_state_dict(torch.load(load_from, map_location="cpu")["model"])
        print(f"{'Resumed' if resume else 'Warm-started'} from {load_from}")
    opt = torch.optim.Adam(net.parameters(), lr=lr, weight_decay=weight_decay)

    metrics_log = []
    if os.path.exists(metrics_path):
        try:
            metrics_log = json.load(open(metrics_path))
        except Exception:
            metrics_log = []
    base_update = metrics_log[-1].get("update", 0) if metrics_log else 0

    lg = None
    if league:
        lg = _League(dev, opponent_sims, league_ismcts, rng)

    def evaluate(engine, to_move):
        actions = engine.legal_actions()
        state = torch.from_numpy(encoder.encode_state(engine, to_move)).to(dev)
        feats = torch.from_numpy(encoder.encode_actions(engine, actions)).to(dev)
        with torch.no_grad():
            logits, value = net(state, feats)
            priors = torch.softmax(logits, dim=-1).cpu().numpy().astype(np.float64)
            v = float(torch.tanh(value).item())
        return actions, priors, v

    def _new_game():
        a, b = rng.sample(deck_ids, 2)
        return GameEngine.new_game(DECKS[a](), DECKS[b](), names=(a, b),
                                   seed=rng.randint(0, 2**31 - 1))

    def _choose(visits, tot, moves, temp_moves_eff):
        if moves < temp_moves_eff:                      # sample ∝ visits (explore)
            return int(np.random.choice(len(visits), p=visits / tot))
        return int(visits.argmax())                     # greedy (exploit)

    def self_play_pure(dir_eff, temp_eff):
        eng = _new_game()
        recs, moves = [], 0
        while not eng.state.is_over() and moves < max_moves:
            me = eng.state.current_player
            root = run_puct(eng, evaluate, sims, c_puct, rng, root_noise=dir_eff)
            visits = root.N; tot = float(visits.sum())
            if tot <= 0 or not root.actions:
                break
            pi = (visits / tot).astype(np.float32)
            recs.append((encoder.encode_state(eng, me),
                         encoder.encode_actions(eng, root.actions), pi, me))
            eng.apply(root.actions[_choose(visits, tot, moves, temp_eff)]); moves += 1
        w = eng.state.winner
        return [(s, f, pi, _outcome(m, w)) for (s, f, pi, m) in recs], moves

    def self_play_league(dir_eff, temp_eff):
        eng = _new_game()
        learner_seat = rng.randint(0, 1)
        opp = lg.sample()
        recs, moves = [], 0
        while not eng.state.is_over() and moves < max_moves:
            me = eng.state.current_player
            if me == learner_seat:
                root = run_puct(eng, evaluate, sims, c_puct, rng, root_noise=dir_eff)
                visits = root.N; tot = float(visits.sum())
                if tot <= 0 or not root.actions:
                    break
                pi = (visits / tot).astype(np.float32)
                recs.append((encoder.encode_state(eng, me),
                             encoder.encode_actions(eng, root.actions), pi))
                eng.apply(root.actions[_choose(visits, tot, moves, temp_eff)])
            else:
                eng.apply(lg.move(opp, eng))
            moves += 1
        w = eng.state.winner
        lg.record(opp, opp_won=(w == (1 - learner_seat)))
        z = _outcome(learner_seat, w)
        return [(s, f, pi, z) for (s, f, pi) in recs], moves

    buffer = deque(maxlen=buffer_size)
    start = time.time()
    lr_final = lr * lr_final_frac
    dir_final = dirichlet * dir_final_frac

    for it in range(start_iter + 1, iters + 1):
        progress = it / max(1, iters)
        # cosine LR decay + linear exploration anneal across the whole run
        lr_t = lr_final + 0.5 * (lr - lr_final) * (1 + math.cos(math.pi * progress))
        for g in opt.param_groups:
            g["lr"] = lr_t
        dir_eff = max(dir_final, dirichlet * (1.0 - progress * (1.0 - dir_final_frac)))
        temp_eff = temp_moves if progress < 0.5 else max(4, temp_moves // 2)

        lengths = []
        for _ in range(games):
            ex, n = (self_play_league if league else self_play_pure)(dir_eff, temp_eff)
            buffer.extend(ex); lengths.append(n)

        data = list(buffer)
        pol_losses, val_losses, ents = [], [], []
        for _ in range(epochs):
            random.shuffle(data)
            for mb_start in range(0, len(data), batch):
                mb = data[mb_start:mb_start + batch]
                opt.zero_grad()
                for s, f, pi, z in mb:
                    state = torch.from_numpy(s).to(dev)
                    feats = torch.from_numpy(f).to(dev)
                    logits, value = net(state, feats)
                    logp = F.log_softmax(logits, dim=-1)
                    target = torch.from_numpy(pi).to(dev)
                    pol_loss = -(target * logp).sum()
                    val_loss = (torch.tanh(value) - float(z)) ** 2
                    (pol_loss + value_coef * val_loss).backward()
                    pol_losses.append(float(pol_loss.item()))
                    val_losses.append(float(val_loss.item()))
                    ents.append(float(-(torch.softmax(logits, -1) * logp).sum().item()))
                torch.nn.utils.clip_grad_norm_(net.parameters(), 1.0)
                opt.step()

        torch.save({"model": net.state_dict()}, out)

        # grow the league with a snapshot of the improved learner
        if league and league_add_every and it % league_add_every == 0:
            lg.add_net(f"snap{it}", {k: v.detach().cpu().clone() for k, v in net.state_dict().items()},
                       league_size)

        winrate = 0.0
        if eval_games:
            from agents.alphazero_agent import AlphaZeroAgent
            from agents.basic_agents import HeuristicAgent
            wins = 0
            for g in range(eval_games):
                az = AlphaZeroAgent(out, iterations=sims); opp = HeuristicAgent()
                a, b = rng.sample(deck_ids, 2)
                e = GameEngine.new_game(DECKS[a](), DECKS[b](), seed=1000 + g)
                ags = {0: az, 1: opp}; p = 0
                while not e.state.is_over() and p < 400:
                    e.apply(ags[e.state.current_player].select(e)); p += 1
                wins += int(e.state.winner == 0)
            winrate = wins / eval_games

        update = base_update + (it - start_iter)
        rec = {
            "update": update,
            "winrate_recent": round(winrate, 3),
            "winrate_update": round(winrate, 3),
            "policy_loss": round(float(np.mean(pol_losses)) if pol_losses else 0.0, 4),
            "value_loss": round(float(np.mean(val_losses)) if val_losses else 0.0, 4),
            "entropy": round(float(np.mean(ents)) if ents else 0.0, 4),
            "episodes": update * games,
            "elapsed_s": round(time.time() - start, 1),
            "opponent": "league" if league else "self(puct)",
            "avg_game_len": round(float(np.mean(lengths)) if lengths else 0.0, 1),
            "examples": len(buffer),
            "lr": round(lr_t, 6),
            "dirichlet": round(dir_eff, 3),
        }
        if league:
            rec["league_size"] = len(lg.members)
        metrics_log.append(rec)
        json.dump(metrics_log, open(metrics_path, "w"), indent=2)
        json.dump({"iters_done": it, "total": iters, "seed": seed,
                   "best_winrate": max((r.get("winrate_recent", 0) for r in metrics_log), default=0),
                   "league": league, "updated": time.time()},
                  open(run_state_path, "w"), indent=2)
        if snapshot_every and update % snapshot_every == 0:
            torch.save({"model": net.state_dict()}, os.path.join(out_dir, f"policy_az_{update}.pt"))
        if league:
            json.dump({"update": update, "members": lg.standings()},
                      open(os.path.join(out_dir, "league.json"), "w"), indent=2)
        print(f"iter {it}/{iters} (upd {update}) | ploss {rec['policy_loss']} "
              f"vloss {rec['value_loss']} ent {rec['entropy']} | len {rec['avg_game_len']} "
              f"| lr {lr_t:.1e} dir {dir_eff:.2f} "
              + (f"| winrate vs heuristic {winrate:.2f} " if eval_games else "")
              + (f"| league[{lg.summary()}] " if league else "")
              + f"| {rec['elapsed_s']}s")

    print(f"Done. Checkpoint: {out}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iters", type=int, default=10, help="TARGET total iterations (with --resume)")
    ap.add_argument("--games", type=int, default=20, help="self-play games per iteration")
    ap.add_argument("--sims", type=int, default=160, help="PUCT simulations per move")
    ap.add_argument("--c-puct", type=float, default=1.5)
    ap.add_argument("--max-moves", type=int, default=120)
    ap.add_argument("--temp-moves", type=int, default=12)
    ap.add_argument("--dirichlet", type=float, default=0.25)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--value-coef", type=float, default=1.0)
    ap.add_argument("--weight-decay", type=float, default=1e-4)
    ap.add_argument("--epochs", type=int, default=2)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--buffer-size", type=int, default=20000)
    ap.add_argument("--out", type=str, default=LATEST)
    ap.add_argument("--warm-start", type=str, default=LATEST)
    ap.add_argument("--scratch", action="store_true")
    ap.add_argument("--device", type=str, default="auto", help="auto|cpu|mps|cuda")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--eval-games", type=int, default=0)
    ap.add_argument("--snapshot-every", type=int, default=0)
    ap.add_argument("--metrics", type=str, default=None)
    ap.add_argument("--resume", action="store_true",
                    help="continue toward --iters using <out_dir>/az_run.json")
    ap.add_argument("--lr-final-frac", type=float, default=0.1)
    ap.add_argument("--dir-final-frac", type=float, default=0.2)
    ap.add_argument("--league", action="store_true", help="train against an exploiter population")
    ap.add_argument("--league-add-every", type=int, default=10, help="snapshot learner into the pool every N iters")
    ap.add_argument("--league-size", type=int, default=6, help="max net snapshots in the pool")
    ap.add_argument("--opponent-sims", type=int, default=0, help="PUCT sims for net opponents (0 = policy argmax)")
    ap.add_argument("--league-ismcts", action="store_true", help="also include ISMCTS as a league baseline")
    a = ap.parse_args()
    train(iters=a.iters, games=a.games, sims=a.sims, c_puct=a.c_puct, max_moves=a.max_moves,
          temp_moves=a.temp_moves, dirichlet=a.dirichlet, lr=a.lr, value_coef=a.value_coef,
          weight_decay=a.weight_decay, epochs=a.epochs, batch=a.batch, buffer_size=a.buffer_size,
          out=a.out, warm_start=a.warm_start, scratch=a.scratch, device=a.device, seed=a.seed,
          eval_games=a.eval_games, snapshot_every=a.snapshot_every, metrics_path=a.metrics,
          resume=a.resume, lr_final_frac=a.lr_final_frac, dir_final_frac=a.dir_final_frac,
          league=a.league, league_add_every=a.league_add_every, league_size=a.league_size,
          opponent_sims=a.opponent_sims, league_ismcts=a.league_ismcts)


if __name__ == "__main__":
    main()
