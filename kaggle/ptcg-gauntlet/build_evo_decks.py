"""Add evolution-line decks (Stage 1 -> Stage 2 ex) to the gauntlet.

These play very differently from the Basic-ex aggro decks: they must set up an
evolution line (Rare Candy included to jump Basic -> Stage 2). Energy is derived
from each attacker's actual best attack cost, so even Dragon lines (which have no
basic energy of their own) get a playable energy base.

Writes into the SAME gauntlet/ folder next to the original 15 (which are left
untouched). Each deck is validated against both the construction rules and the
engine; only engine-accepted decks are kept.
"""
import os
from collections import Counter
from cg.api import all_card_data, all_attack
from cg.game import battle_start, battle_finish

C = {c.cardId: c for c in all_card_data()}
A = {a.attackId: a for a in all_attack()}

RARE_CANDY = 1079
# basic energy id by EnergyType int
BASIC_BY_TYPE = {1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 7, 8: 8}

# Shared non-ACE Trainer package (same staples as the base gauntlet). 32 cards.
PACKAGE = [
    (1121, 4), (1086, 3), (1102, 2), (1122, 2), (1119, 2), (1097, 3),
    (1123, 3), (1182, 2), (1205, 3), (1235, 3), (1227, 3), (1213, 2),
]

# (name, basic_id, stage1_id, stage2_id, ace_id) — diverse, distinct types.
EVO_SPECS = [
    ("salamence_dragon",   300, 301, 302, 1158),
    ("cinderace_fire",     151, 152, 153, 1088),
    ("slaking_colorless",  998, 999, 232, 1125),
    ("garchomp_fighting",  379, 380, 381, 1158),
    ("luxray_lightning",  1035, 1036, 954, 1088),
    ("decidueye_grass",    127, 128, 1022, 1158),
    ("nidoking_dark",      453, 454, 455, 1088),
    ("empoleon_metal",     804, 805, 835, 1158),
    ("dragapult_dragon",   119, 120, 121, 1125),
    ("hydreigon_dark",     227, 228, 229, 1088),
    ("mamoswine_fighting", 281, 282, 283, 1158),
    ("greninja_water",      33,  34,  40, 1125),
    ("serperior_grass",    479, 480, 481, 1158),
    ("blaziken_fire",      324, 325, 326, 1088),
]


def derive_energy(card):
    """Basic-energy id(s) implied by the card's best damaging attack cost.
    Returns a list of (energy_id, weight); colorless-only falls back to Water."""
    best, best_types = None, []
    for aid in getattr(card, "attacks", []) or []:
        a = A.get(aid)
        if not a or a.damage <= 0:
            continue
        types = [int(e) for e in (a.energies or []) if int(e) in BASIC_BY_TYPE]
        if best is None or a.damage > best:
            best, best_types = a.damage, types
    if not best_types:
        return [(BASIC_BY_TYPE[3], 1)]  # colorless attacker -> Water base
    cnt = Counter(best_types)
    return [(BASIC_BY_TYPE[t], n) for t, n in cnt.items()]


def is_ace(cid):
    c = C.get(cid)
    return bool(c) and bool(getattr(c, "aceSpec", False))


def is_basic_pokemon(cid):
    c = C.get(cid)
    return bool(c) and int(c.cardType) == 0 and bool(getattr(c, "basic", False))


def build_evo(basic, s1, s2, ace_id):
    cards = [basic] * 4 + [s1] * 2 + [s2] * 3 + [RARE_CANDY] * 3  # 12 line cards
    for cid, n in PACKAGE:
        cards += [cid] * n
    if ace_id is not None:
        cards.append(ace_id)
    # Fill to 60 with the derived energy base (split across required types).
    energy = derive_energy(C[s2])
    total_w = sum(w for _, w in energy)
    slots = 60 - len(cards)
    i = 0
    filled = []
    for eid, w in energy:
        k = round(slots * w / total_w)
        filled += [eid] * k
    while len(filled) < slots:
        filled.append(energy[0][0])
    filled = filled[:slots]
    return cards + filled


def rules_ok(deck):
    if len(deck) != 60:
        return False, f"size {len(deck)}"
    cnt = Counter(deck)
    for cid, n in cnt.items():
        c = C.get(cid)
        if c is None:
            return False, f"unknown id {cid}"
        if int(c.cardType) != 5 and n > 4:
            return False, f"{n}x {c.name}"
    if sum(1 for cid in deck if is_ace(cid)) > 1:
        return False, "multiple ACE SPEC"
    if not any(is_basic_pokemon(cid) for cid in deck):
        return False, "no Basic Pokemon"
    return True, "ok"


def engine_ok(deck):
    try:
        obs, sd = battle_start(deck, deck)
        ok = obs is not None and getattr(sd, "errorType", 0) == 0
        battle_finish()
        return ok
    except Exception:
        try:
            battle_finish()
        except Exception:
            pass
        return False


def main():
    os.makedirs("gauntlet", exist_ok=True)
    kept, rejected = [], []
    for name, b, s1, s2, ace in EVO_SPECS:
        deck = build_evo(b, s1, s2, ace)
        rok, why = rules_ok(deck)
        if not rok:
            rejected.append((name, "rules:" + why))
            continue
        if not engine_ok(deck):
            rejected.append((name, "engine-rejected"))
            continue
        with open(os.path.join("gauntlet", f"{name}.csv"), "w") as fh:
            fh.write("\n".join(str(x) for x in deck) + "\n")
        kept.append(name)
    print(f"KEPT {len(kept)} evolution decks:")
    for n in kept:
        print("  +", n)
    if rejected:
        print(f"REJECTED {len(rejected)}:")
        for n, why in rejected:
            print("  -", n, why)
    print(f"gauntlet now has {len(os.listdir('gauntlet'))} decks total")


if __name__ == "__main__":
    main()
