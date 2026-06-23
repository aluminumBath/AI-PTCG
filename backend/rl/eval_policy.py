"""Evaluate a *deployed* agent vs the heuristic — the honest "policy health" signal.

The raw policy net's PPO win rate understates what actually ships: the deployed
agents (AlphaZero, RL-MCTS) wrap the net in PUCT search + the never-miss-lethal
Closer, which is much stronger. This plays the chosen agent against the heuristic
over N games with **alternating seats** and random decks, and writes the aggregate
win rate to ``checkpoints/policy_eval.json``. ``--append`` accumulates across runs,
so a long, fair eval can be split into several invocations.

Offline tool; not part of any competition submission.

    python -m rl.eval_policy --agent alphazero --sims 160 --games 12 --append
"""
from __future__ import annotations

import argparse
import json
import os
import random
import time

CKPT_DIR = os.environ.get("CKPT_DIR", os.path.join(os.path.dirname(__file__), "..", "checkpoints"))
OUT = os.path.join(CKPT_DIR, "policy_eval.json")


def _build(agent_id: str, sims: int, ckpt):
    if agent_id == "alphazero":
        from agents.alphazero_agent import AlphaZeroAgent
        return AlphaZeroAgent(ckpt, iterations=sims)
    if agent_id == "rl_mcts":
        from agents.rl_mcts_agent import RLGuidedMCTSAgent
        return RLGuidedMCTSAgent(iterations=sims, checkpoint=ckpt)
    from agents.registry import make_agent
    return make_agent(agent_id, ckpt)


def run(agent_id="alphazero", sims=160, games=12, append=False, out=OUT, seed=0,
        ckpt=None, max_plies=400):
    from agents.basic_agents import HeuristicAgent
    from engine.game import GameEngine
    from data.cards_db import DECKS

    ckpt = ckpt or os.path.join(CKPT_DIR, "policy_latest.pt")
    rng = random.Random(seed if not append else (seed + int(time.time()) % 100000))
    deck_ids = list(DECKS.keys())
    agent = _build(agent_id, sims, ckpt)
    opp = HeuristicAgent(rng)

    wins = 0
    for g in range(games):
        seat = g % 2                                   # alternate seats for fairness
        a, b = rng.sample(deck_ids, 2)
        eng = GameEngine.new_game(DECKS[a](), DECKS[b](), seed=rng.randint(0, 2**31 - 1))
        ags = {seat: agent, 1 - seat: opp}
        p = 0
        while not eng.state.is_over() and p < max_plies:
            eng.apply(ags[eng.state.current_player].select(eng)); p += 1
        if eng.state.winner == seat:
            wins += 1
        print(f"  game {g + 1}/{games}: {'WIN' if eng.state.winner == seat else 'loss'} "
              f"(seat {seat}, {a} vs {b})")

    tot_w, tot_g = wins, games
    if append and os.path.exists(out):
        try:
            prev = json.load(open(out))
            if prev.get("agent") == agent_id and prev.get("sims") == sims:
                tot_w += int(prev.get("wins", 0)); tot_g += int(prev.get("games", 0))
        except Exception:
            pass
    rec = {"agent": agent_id, "sims": sims, "games": tot_g, "wins": tot_w,
           "winrate": round(tot_w / tot_g, 3) if tot_g else 0.0,
           "opponent": "heuristic", "updated": time.time()}
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    json.dump(rec, open(out, "w"), indent=2)
    print(f"{agent_id} ({sims} sims) vs heuristic: {rec['winrate']:.0%} over {tot_g} games -> {out}")
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", type=str, default="alphazero")
    ap.add_argument("--sims", type=int, default=160)
    ap.add_argument("--games", type=int, default=12)
    ap.add_argument("--append", action="store_true", help="accumulate into existing policy_eval.json")
    ap.add_argument("--out", type=str, default=OUT)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--checkpoint", type=str, default=None)
    a = ap.parse_args()
    run(agent_id=a.agent, sims=a.sims, games=a.games, append=a.append, out=a.out,
        seed=a.seed, ckpt=a.checkpoint)


if __name__ == "__main__":
    main()
