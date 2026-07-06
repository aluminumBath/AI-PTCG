"""Evaluate the search agent against the deck gauntlet.

(A) SKILL TEST  - for each gauntlet deck, play search-vs-heuristic with BOTH
    sides piloting that same deck. Isolates agent skill across many different
    strategies (the non-mirror signal the single-deck test couldn't give).

(B) DECK TEST   - play the search agent on our Mega Abomasnow ex submission deck
    against the heuristic agent on each gauntlet deck. Shows our deck's matchup
    spread across the field.

The agent's forward search seeds its own hidden cards from its decklist; we set
that per game via the module's _DECK_CACHE so seeding always matches the deck it
is actually piloting.
"""
import glob
import importlib.util
import os
import sys
import time


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


SEARCH = load("search_agent", "main.py")
HEUR = load("heur_agent", "agent_heur.py")
from cg.game import battle_start, battle_finish  # noqa: E402
import cg.game as CG  # noqa: E402


def read_deck(path):
    return [int(x) for x in open(path).read().split() if x.strip()]


ABOMASNOW = read_deck("deck.csv")
GAUNTLET = {os.path.splitext(os.path.basename(p))[0]: read_deck(p)
            for p in sorted(glob.glob("gauntlet/*.csv"))}


def play(agent0, agent1, deck0, deck1, seed0=None, seed1=None, max_sel=4000):
    """Play one game. seedN = decklist the agentN uses for its own search
    seeding (defaults to that side's deck)."""
    SEARCH._DECK_CACHE = seed0 if seed0 is not None else deck0
    # HEUR ignores its cache, but keep it coherent anyway.
    HEUR._DECK_CACHE = seed1 if seed1 is not None else deck1
    obs, sd = battle_start(deck0, deck1)
    if obs is None:
        return ("nostart", getattr(sd, "errorType", None))
    n = 0
    try:
        while obs is not None:
            cur = obs.get("current")
            if cur is not None:
                r = cur.get("result", -1)
                if r is not None and r >= 0:
                    return r
            who = cur.get("yourIndex", 0) if cur is not None else 0
            # agent0 seeds from deck0; agent1 from deck1. Reset per call because
            # both agents share the same SEARCH module cache within a game only
            # one of them is the search agent, so set it to whichever is acting.
            if who == 0 and agent0 is SEARCH.agent:
                SEARCH._DECK_CACHE = seed0 if seed0 is not None else deck0
            elif who == 1 and agent1 is SEARCH.agent:
                SEARCH._DECK_CACHE = seed1 if seed1 is not None else deck1
            pick = agent0(obs) if who == 0 else agent1(obs)
            obs = CG.battle_select(pick)
            n += 1
            if n > max_sel:
                return "timeout"
        return "obs_none"
    finally:
        battle_finish()


def skill_test(n_each=8):
    print("=== (A) SKILL TEST: search vs heuristic, per gauntlet deck ===")
    tot_s = tot_h = tot_o = 0
    for name, deck in GAUNTLET.items():
        s = h = o = 0
        for _ in range(n_each):
            w = play(SEARCH.agent, HEUR.agent, deck, deck)
            if w == 0:
                s += 1
            elif w == 1:
                h += 1
            else:
                o += 1
        for _ in range(n_each):
            w = play(HEUR.agent, SEARCH.agent, deck, deck)
            if w == 1:
                s += 1
            elif w == 0:
                h += 1
            else:
                o += 1
        tot_s += s
        tot_h += h
        tot_o += o
        dec = s + h
        wr = (s / dec * 100) if dec else 0.0
        print(f"  {name:22} search {s:2}/{dec:2}  ({wr:5.1f}%)" + (f"  [{o} anom]" if o else ""))
    dec = tot_s + tot_h
    print(f"  {'TOTAL':22} search {tot_s}/{dec}  ({tot_s/dec*100:.1f}%)   anomalies: {tot_o}")


def deck_test(n_each=4):
    print("=== (B) DECK TEST: Abomasnow(search) vs each gauntlet deck(heuristic) ===")
    tot_w = tot_l = tot_o = 0
    for name, deck in GAUNTLET.items():
        w = l = o = 0
        for _ in range(n_each):  # Abomasnow as player 0
            r = play(SEARCH.agent, HEUR.agent, ABOMASNOW, deck, seed0=ABOMASNOW)
            if r == 0:
                w += 1
            elif r == 1:
                l += 1
            else:
                o += 1
        for _ in range(n_each):  # Abomasnow as player 1
            r = play(HEUR.agent, SEARCH.agent, deck, ABOMASNOW, seed1=ABOMASNOW)
            if r == 1:
                w += 1
            elif r == 0:
                l += 1
            else:
                o += 1
        tot_w += w
        tot_l += l
        tot_o += o
        dec = w + l
        wr = (w / dec * 100) if dec else 0.0
        print(f"  vs {name:22} {w:2}-{l:2}  ({wr:5.1f}%)" + (f"  [{o} anom]" if o else ""))
    dec = tot_w + tot_l
    print(f"  {'OVERALL':25} {tot_w}-{tot_l}  ({tot_w/dec*100:.1f}%)   anomalies: {tot_o}")


if __name__ == "__main__":
    t0 = time.monotonic()
    which = sys.argv[1] if len(sys.argv) > 1 else "both"
    if which in ("skill", "both"):
        skill_test(int(sys.argv[2]) if len(sys.argv) > 2 else 8)
    if which in ("deck", "both"):
        deck_test(int(sys.argv[3]) if len(sys.argv) > 3 else 4)
    print(f"[{time.monotonic()-t0:.1f}s]")
