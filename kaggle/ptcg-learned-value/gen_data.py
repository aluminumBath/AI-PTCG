"""Generate a self-play dataset for the value net.

Plays heuristic self-play (the shipped agent with search OFF, for speed) across a
spread of decks, and at every MAIN decision records the acting player's board
features labelled with that game's eventual outcome (win=1 / loss=0). This is the
standard value-target setup: every position is labelled with the final result, and
the net learns P(win | board) once enough games average out the label noise.

Splitting is by GAME (a group id per game) so training never sees positions from a
game whose outcome it is validated on.

    python3 gen_data.py [num_games] [out.npz]
"""
import glob
import os
import random
import sys

import numpy as np

import main as A
A._USE_SEARCH = False  # heuristic behaviour policy: fast, decent, diverse

import value_net as V
from cg.game import battle_start, battle_select, battle_finish


def read(p):
    return [int(x) for x in open(p).read().split() if x.strip()]


def deck_pool():
    pool = {"abomasnow": read("deck.csv")}
    want = ["pikachu_lightning", "gouging_fire", "koraidon_fighting", "mewtwo_rocket",
            "yveltal_dark", "salamence_dragon", "dragapult_dragon", "garchomp_fighting",
            "empoleon_metal", "mega_dragonite_dragon", "mega_gengar_dark", "greninja_water",
            "vaporeon_water", "zapdos_lightning", "hops_zacian_metal"]
    for w in want:
        p = f"gauntlet/{w}.csv"
        if os.path.exists(p):
            pool[w] = read(p)
    return list(pool.values())


def one_game(d0, d1, gid, X, Y, G, max_sel=4000):
    obs = battle_start(d0, d1)[0]
    if obs is None:
        return
    pending = []  # (feature_vec, who)
    n = 0
    winner = None
    while obs is not None:
        cur = obs.get("current")
        if cur is not None:
            r = cur.get("result", -1)
            if r is not None and r >= 0:
                winner = r
                break
        try:
            O = A.to_observation_class(obs)
            st, sel = O.current, O.select
            if st is not None and sel is not None and A._is_main_sel(sel):
                who = st.yourIndex
                pending.append((V.features(st, who), who))
        except Exception:
            pass
        try:
            obs = battle_select(A.agent(obs))
        except Exception:
            break
        n += 1
        if n > max_sel:
            break
    if winner not in (0, 1):
        return  # unfinished / draw -> discard (no clean label)
    for feat, who in pending:
        X.append(feat)
        Y.append(1.0 if who == winner else 0.0)
        G.append(gid)


def main():
    games = int(sys.argv[1]) if len(sys.argv) > 1 else 120
    out = sys.argv[2] if len(sys.argv) > 2 else "data.npz"
    random.seed(0)
    pool = deck_pool()
    X, Y, G = [], [], []
    kept = 0
    for gid in range(games):
        d0 = random.choice(pool)
        d1 = random.choice(pool)
        before = len(X)
        try:
            one_game(d0, d1, gid, X, Y, G)
        except Exception:
            pass
        finally:
            try:
                battle_finish()
            except Exception:
                pass
        if len(X) > before:
            kept += 1
        if (gid + 1) % 20 == 0:
            print(f"  {gid+1}/{games} games, {len(X)} samples "
                  f"({kept} finished)", flush=True)
    X = np.asarray(X, dtype=np.float32)
    Y = np.asarray(Y, dtype=np.float32)
    G = np.asarray(G, dtype=np.int32)
    np.savez(out, X=X, y=Y, groups=G, names=np.array(V.FEATURE_NAMES))
    print(f"saved {out}: X={X.shape} pos-rate={Y.mean():.3f} "
          f"games_kept={kept}/{games}")


if __name__ == "__main__":
    main()
