"""A/B harness for the multi-turn lookahead scaffolding.

Loads the multi-turn agent TWICE — once at the horizon under test, once at
horizon 0 (identical code path, single-turn) — so the comparison isolates the
*effect of the horizon* and nothing else. Runs them head to head, both sides
piloting the same deck, across a chosen slice of the gauntlet.

Run from a copy of the Simulation bundle that also has `agent_multiturn.py` and a
`gauntlet/` folder of decks:

    python3 multiturn_eval.py [horizon] [games_per_deck] [deck_substring]

Examples:
    python3 multiturn_eval.py 1 4 mega      # horizon-1 vs single-turn, mega decks
    python3 multiturn_eval.py 2 6           # horizon-2 vs single-turn, setup decks
    python3 multiturn_eval.py 1 4 aggro     # sanity: should stay ~50% on aggro
"""
import glob
import importlib.util
import os
import sys
import time

import cg.game as CG
from cg.game import battle_start, battle_finish


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def read(p):
    return [int(x) for x in open(p).read().split() if x.strip()]


# Default deck slice: setup-heavy archetypes, where lookahead should matter most.
DEFAULT_SETUP = (
    "salamence_dragon dragapult_dragon cinderace_fire garchomp_fighting "
    "empoleon_metal mega_dragonite_dragon mega_emboar_fire mega_gengar_dark"
).split()


def play(a0, m0, a1, m1, d0, d1, max_sel=4000):
    """One game. a0/a1 are agent fns, m0/m1 their modules (for deck-cache
    seeding), d0/d1 their decks. Each module's _DECK_CACHE is set to the deck of
    whichever side is currently acting."""
    obs, sd = battle_start(d0, d1)
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
            if who == 0:
                m0._DECK_CACHE = d0
                pick = a0(obs)
            else:
                m1._DECK_CACHE = d1
                pick = a1(obs)
            obs = CG.battle_select(pick)
            n += 1
            if n > max_sel:
                return ("timeout", n)
        return "obs_none"
    finally:
        battle_finish()


def main():
    horizon = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    games = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    filt = sys.argv[3] if len(sys.argv) > 3 else None

    A = load("mt_test", "agent_multiturn.py")
    A._MULTITURN_HORIZON = horizon
    B = load("mt_base", "agent_multiturn.py")
    B._MULTITURN_HORIZON = 0  # single-turn baseline (same code path)

    decks = {os.path.splitext(os.path.basename(p))[0]: read(p)
             for p in sorted(glob.glob("gauntlet/*.csv"))}
    names = [n for n in (decks or {}) if (filt in n if filt else n in DEFAULT_SETUP)]
    if not names:
        names = list(decks)[:8]

    print(f"multi-turn horizon {horizon} vs single-turn (horizon 0) | "
          f"{len(names)} decks x {games*2} games")
    tw = bw = an = 0
    t0 = time.monotonic()
    for name in names:
        d = decks[name]
        w = l = o = 0
        for _ in range(games):
            r = play(A.agent, A, B.agent, B, d, d); w += (r == 0); l += (r == 1); o += (r not in (0, 1))
        for _ in range(games):
            r = play(B.agent, B, A.agent, A, d, d); w += (r == 1); l += (r == 0); o += (r not in (0, 1))
        tw += w; bw += l; an += o
        tot = w + l or 1
        print(f"  {name:22} multi-turn {w:2d}/{w+l:<2d} ({w/tot*100:4.0f}%)"
              + (f"  [{o} anom]" if o else ""))
    tot = tw + bw or 1
    print(f"TOTAL multi-turn {tw}/{tot} ({tw/tot*100:.1f}%)  anomalies {an}  "
          f"({time.monotonic()-t0:.0f}s)")
    print(">50% means the horizon helped on this slice; ~50% means no gain yet.")


if __name__ == "__main__":
    main()
