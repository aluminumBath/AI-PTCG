"""Add three more archetypes to the gauntlet:
  * Stage-1 ex lines (Basic -> Stage 1 ex)
  * non-ex single-prize big-Basic decks (different prize math)
  * Mega ex lines (Basic -> [Stage 1 ->] Mega ex; Rare Candy for 3-card lines)

Reuses the validated builder logic (energy derivation, rules + engine checks,
Trainer package) from build_evo_decks. Evolution lines are traced automatically
via evolvesFrom; energy is derived from each attacker's real attack cost.
Only decks accepted by BOTH the rules and the engine are written to gauntlet/.
"""
import os
from collections import Counter
from cg.api import all_card_data, all_attack
from build_evo_decks import (
    C, PACKAGE, RARE_CANDY, derive_energy, rules_ok, engine_ok,
)

A = {a.attackId: a for a in all_attack()}
BY_NAME = {}
for _c in C.values():
    if int(_c.cardType) == 0:
        BY_NAME.setdefault(_c.name, []).append(_c)


def find(name, prefer_basic=False):
    cands = BY_NAME.get(name, [])
    if prefer_basic:
        for c in cands:
            if getattr(c, "basic", False):
                return c
    return cands[0] if cands else None


def trace_line(final_id):
    """Return [basic, ..., final] card-ids by walking evolvesFrom, or None."""
    c = C.get(final_id)
    if c is None:
        return None
    line = [c]
    cur = c
    guard = 0
    while getattr(cur, "evolvesFrom", None) and guard < 4:
        pre = find(cur.evolvesFrom, prefer_basic=(guard == 0 or True))
        if pre is None or pre.cardId in [x.cardId for x in line]:
            break
        line.append(pre)
        cur = pre
        guard += 1
    line.reverse()
    return [x.cardId for x in line]


def fill_energy(cards, from_card):
    energy = derive_energy(from_card)
    total_w = sum(w for _, w in energy)
    slots = 60 - len(cards)
    out = []
    for eid, w in energy:
        out += [eid] * round(slots * w / total_w)
    while len(out) < slots:
        out.append(energy[0][0])
    return cards + out[:slots]


def build_line_deck(final_id, ace_id):
    line = trace_line(final_id)
    if not line:
        return None
    basic = line[0]
    final = line[-1]
    if len(line) <= 1:  # basic mega/ex, no evolution needed
        cards = [basic] * 4
    elif len(line) == 2:  # Basic -> ex (like Abomasnow): 4 + 4
        cards = [line[0]] * 4 + [line[1]] * 4
    else:  # Basic -> Stage1 -> final: line + Rare Candy
        cards = [line[0]] * 4 + [line[1]] * 2 + [line[-1]] * 3 + [RARE_CANDY] * 3
    for cid, n in PACKAGE:
        cards += [cid] * n
    if ace_id is not None:
        cards.append(ace_id)
    return fill_energy(cards, C[final])


def build_nonex_deck(anchors, ace_id):
    cards = []
    for cid, n in anchors:
        cards += [cid] * n
    for cid, n in PACKAGE:
        cards += [cid] * n
    if ace_id is not None:
        cards.append(ace_id)
    lead = C[anchors[0][0]]
    return fill_energy(cards, lead)


# --- Stage-1 ex (final-form id, ace) ---
STAGE1_EX = [
    ("vaporeon_water", 241, 1125), ("flareon_fire", 239, 1088),
    ("jolteon_lightning", 244, 1088), ("leafeon_grass", 236, 1158),
    ("ceruledge_fire", 320, 1088), ("palafin_water", 107, 1125),
    ("bellibolt_lightning", 269, 1088), ("archaludon_metal", 190, 1158),
    ("mabosstiff_dark", 389, 1088), ("yanmega_grass", 340, 1158),
    ("excadrill_fighting", 527, 1158), ("electivire_lightning", 372, 1088),
]

# --- Mega ex (final-form id, ace) ---
MEGA_EX = [
    ("mega_lucario_fighting", 678, 1158), ("mega_manectric_lightning", 737, 1088),
    ("mega_starmie_water", 1031, 1125), ("mega_venusaur_grass", 652, 1158),
    ("mega_dragonite_dragon", 904, 1125), ("mega_emboar_fire", 932, 1088),
    ("mega_feraligatr_water", 939, 1125), ("mega_gengar_dark", 772, 1088),
    ("mega_camerupt_fire", 662, 1088),
]

# --- non-ex single-prize (name, anchors, ace) ---
NONEX = [
    ("ns_zekrom_lightning", [(906, 4), (953, 4)], 1088),
    ("reshiram_fire", [(794, 4), (58, 3)], 1088),
    ("tapu_bulu_grass", [(920, 4)], 1158),
    ("dialga_dragon", [(195, 4), (87, 3)], 1125),
    ("great_tusk_fighting", [(58, 4)], 1158),
    ("iron_boulder_psychic", [(971, 4)], 1125),
    ("zapdos_lightning", [(953, 4), (906, 3)], 1088),
]


def process(kind, specs, builder):
    kept, rej = [], []
    for entry in specs:
        name = entry[0]
        try:
            if kind == "nonex":
                deck = builder(entry[1], entry[2])
            else:
                deck = builder(entry[1], entry[2])
        except Exception as e:
            rej.append((name, f"build-error:{e!r}"))
            continue
        if deck is None:
            rej.append((name, "no-line"))
            continue
        ok, why = rules_ok(deck)
        if not ok:
            rej.append((name, "rules:" + why))
            continue
        if not engine_ok(deck):
            rej.append((name, "engine-rejected"))
            continue
        with open(os.path.join("gauntlet", f"{name}.csv"), "w") as fh:
            fh.write("\n".join(str(x) for x in deck) + "\n")
        kept.append(name)
    return kept, rej


def main():
    os.makedirs("gauntlet", exist_ok=True)
    allk, allr = [], []
    for kind, specs, b in [
        ("stage1", STAGE1_EX, build_line_deck),
        ("mega", MEGA_EX, build_line_deck),
        ("nonex", NONEX, build_nonex_deck),
    ]:
        k, r = process(kind, specs, b)
        print(f"[{kind}] kept {len(k)}: {', '.join(k)}")
        if r:
            print(f"[{kind}] rejected {len(r)}: {r}")
        allk += k
        allr += r
    print(f"\nADDED {len(allk)} decks; gauntlet now has {len(os.listdir('gauntlet'))} total")


if __name__ == "__main__":
    main()
