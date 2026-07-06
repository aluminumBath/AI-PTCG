"""Shared feature extraction and the pure-numpy learned value.

`features(state, me)` turns a board (the same structured `state` object the agent's
`_eval` receives) into a fixed-length vector of the raw signals `_eval` is built
from -- prizes, active HP/energy/threat, board width, resources -- but WITHOUT the
hand-tuned weights. A logistic-regression value net then learns those weights from
self-play outcomes. Because the model is linear, inference is a single dot product
(`value` below), so the trained value drops into the agent with no sklearn
dependency -- it is competition-deployable.

Helpers (card DB, damage math) are reused from the shipped agent module so the
features stay perfectly consistent with how the agent scores boards.
"""
import json

import numpy as np

import main as A  # shipped agent: card DB + damage helpers (import has no side effects)

FEATURE_NAMES = [
    "prize_diff", "my_prize", "opp_prize",
    "opp_active_dmg", "opp_active_hp_frac", "opp_active_ko",
    "my_threat", "my_threat_lethal",
    "my_active_dmg", "my_active_hp_frac", "my_active_energy", "my_active_pokevalue",
    "incoming_threat", "incoming_lethal", "weakness_exposed",
    "opp_active_energy", "opp_active_pokevalue",
    "my_status", "opp_status",
    "my_bench", "opp_bench", "my_bench_best",
    "my_hand", "opp_hand",
    "my_total_energy", "opp_total_energy",
    "my_poke_count", "opp_poke_count",
    "turn",
]
N_FEATURES = len(FEATURE_NAMES)


def _incoming(attacker, defender):
    """Best damage `attacker` could deal `defender` allowing one energy attach."""
    if attacker is None or defender is None:
        return 0.0
    c = A._card(getattr(attacker, "id", None))
    if not c:
        return 0.0
    budget = len(getattr(attacker, "energies", []) or []) + 1
    best = 0.0
    for aid in getattr(c, "attacks", []) or []:
        a = A._ATTACKS.get(aid)
        if not a or len(getattr(a, "energies", []) or []) > budget:
            continue
        d = A._effective_damage(aid, attacker, defender)
        if d > best:
            best = d
    return best


def _status(ps):
    return sum(1 for f in ("asleep", "paralyzed", "confused", "poisoned", "burned")
               if getattr(ps, f, False))


def _energy_total(ps):
    tot = 0
    if ps.active and ps.active[0] is not None:
        tot += len(getattr(ps.active[0], "energies", []) or [])
    for p in ps.bench:
        tot += len(getattr(p, "energies", []) or [])
    return tot


def _hpfrac(c):
    mh = getattr(c, "maxHp", 0) or 1
    return (getattr(c, "hp", 0) or 0) / mh


def features(state, me):
    """Fixed-length feature vector from `me`'s perspective. Missing pieces (empty
    active, etc.) map to zeros, so it never raises on a partial board."""
    opp = 1 - me
    mp = state.players[me]
    op = state.players[opp]
    ma = mp.active[0] if mp.active else None
    oa = op.active[0] if op.active else None

    my_threat = A._best_ready_damage(ma, oa) if (ma and oa) else 0.0
    inc = _incoming(oa, ma) if (ma and oa) else 0.0
    weak = 0.0
    if ma and oa:
        mc, oc = A._card(ma.id), A._card(oa.id)
        if mc and oc and mc.weakness is not None and \
                int(mc.weakness) == int(getattr(oc, "energyType", -999)):
            weak = 1.0

    f = [
        len(op.prize) - len(mp.prize), float(len(mp.prize)), float(len(op.prize)),
        (getattr(oa, "maxHp", 0) - getattr(oa, "hp", 0)) / 100.0 if oa else 0.0,
        _hpfrac(oa) if oa else 0.0,
        1.0 if (oa and getattr(oa, "hp", 1) <= 0) else 0.0,
        my_threat / 100.0,
        1.0 if (oa and my_threat >= getattr(oa, "hp", 1e9)) else 0.0,
        (getattr(ma, "maxHp", 0) - getattr(ma, "hp", 0)) / 100.0 if ma else 0.0,
        _hpfrac(ma) if ma else 0.0,
        float(len(getattr(ma, "energies", []) or [])) if ma else 0.0,
        float(A._poke_value(ma)) if ma else 0.0,
        inc / 100.0,
        1.0 if (ma and inc >= getattr(ma, "hp", 1e9)) else 0.0,
        weak,
        float(len(getattr(oa, "energies", []) or [])) if oa else 0.0,
        float(A._poke_value(oa)) if oa else 0.0,
        float(_status(mp)), float(_status(op)),
        float(len(mp.bench)), float(len(op.bench)),
        max([float(A._poke_value(p)) for p in mp.bench], default=0.0),
        float(mp.handCount), float(op.handCount),
        float(_energy_total(mp)), float(_energy_total(op)),
        1.0 + len(mp.bench), 1.0 + len(op.bench),
        float(getattr(state, "turn", 0)),
    ]
    return np.asarray(f, dtype=np.float32)


# --------------------------------------------------------------------------- #
# Inference: load exported weights and score a board as P(win) -- pure numpy.
def load_weights(path):
    d = json.load(open(path))
    return {
        "mean": np.asarray(d["mean"], dtype=np.float64),
        "scale": np.asarray(d["scale"], dtype=np.float64),
        "coef": np.asarray(d["coef"], dtype=np.float64),
        "intercept": float(d["intercept"]),
    }


def value(w, state, me):
    """P(win) for `me` at this board, from the exported linear value net."""
    x = (features(state, me).astype(np.float64) - w["mean"]) / w["scale"]
    z = float(np.dot(w["coef"], x) + w["intercept"])
    if z >= 0:
        return 1.0 / (1.0 + np.exp(-z))
    ez = np.exp(z)
    return ez / (1.0 + ez)
