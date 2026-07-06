"""Build a diverse gauntlet of *legal* 60-card decks for the custom cg card set.

Each deck = a Basic-ex attacker core (guaranteed coherent: no evolution pieces
can be missing) + a shared non-ACE Trainer package + basic energy to 60, with an
optional single ACE SPEC. Every deck is checked against BOTH:
  (1) the deck-construction rules (exactly 60; <=4 copies except basic energy;
      <=1 ACE SPEC total; >=1 Basic Pokemon; all IDs valid), and
  (2) the real engine (battle_start must accept it) -- the ultimate arbiter.

Only decks that pass both are written to gauntlet/ as 60 bare card-IDs.
"""
import os
from cg.api import all_card_data
from cg.game import battle_start, battle_finish

C = {c.cardId: c for c in all_card_data()}

BASIC_ENERGY = {"G": 1, "R": 2, "W": 3, "L": 4, "P": 5, "F": 6, "D": 7, "M": 8}

# Shared non-ACE Trainer package (all proven-valid IDs; each <=4). 32 cards.
PACKAGE = [
    (1121, 4),  # Ultra Ball        - search a Pokemon
    (1086, 3),  # Buddy-Buddy Poffin - search Basics
    (1102, 2),  # Dusk Ball
    (1122, 2),  # Pokegear 3.0      - find a Supporter
    (1119, 2),  # Energy Search
    (1097, 3),  # Night Stretcher   - recover
    (1123, 3),  # Switch
    (1182, 2),  # Boss's Orders     - gust
    (1205, 3),  # Cyrano            - supporter (proven)
    (1235, 3),  # Waitress          - supporter (proven)
    (1227, 3),  # Lillie's Determination (proven)
    (1213, 2),  # Judge             - disruption draw
]


def is_ace(cid):
    c = C.get(cid)
    return bool(c) and bool(getattr(c, "aceSpec", False))


def is_basic_pokemon(cid):
    c = C.get(cid)
    return bool(c) and int(c.cardType) == 0 and bool(getattr(c, "basic", False))


def build(anchors, energy_key, ace_id=None):
    cards = []
    for cid, n in anchors:
        cards += [cid] * n
    for cid, n in PACKAGE:
        cards += [cid] * n
    if ace_id is not None:
        cards.append(ace_id)
    fill = BASIC_ENERGY[energy_key]
    while len(cards) < 60:
        cards.append(fill)
    return cards[:60]


def rules_ok(deck):
    """Return (ok, reason)."""
    if len(deck) != 60:
        return False, f"size {len(deck)}"
    from collections import Counter
    cnt = Counter(deck)
    for cid, n in cnt.items():
        c = C.get(cid)
        if c is None:
            return False, f"unknown id {cid}"
        if int(c.cardType) != 5 and n > 4:  # basic energy exempt from the 4-copy cap
            return False, f"{n}x {c.name}"
    if sum(1 for cid in deck if is_ace(cid)) > 1:
        return False, "multiple ACE SPEC"
    if not any(is_basic_pokemon(cid) for cid in deck):
        return False, "no Basic Pokemon"
    return True, "ok"


def engine_ok(deck):
    """The real test: does the engine accept this deck at battle start?"""
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


# (name, anchors[(id,count)], energy_key, ace_id)  -- diverse across all types.
SPECS = [
    ("pikachu_lightning",   [(210, 4), (515, 3), (37, 2)], "L", 1158),   # Pikachu/Zekrom/Iron Thorns
    ("gouging_fire",        [(46, 4), (573, 3), (357, 2)], "R", 1088),   # Gouging Fire/Reshiram/Ho-Oh
    ("black_kyurem_water",  [(179, 4), (509, 3), (944, 2)], "W", 1158),  # Black Kyurem/Kyurem/Regice
    ("bloodmoon_colorless", [(44, 4), (176, 3), (337, 2)], "W", 1125),   # Ursaluna/Terapagos/Lugia
    ("hops_zacian_metal",   [(299, 4), (336, 3), (988, 2)], "M", 1158),  # Hop's Zacian/Zacian/Registeel
    ("miraidon_dragon",     [(313, 4), (957, 3)], "L", 1088),            # Miraidon line
    ("yveltal_dark",        [(1062, 4), (139, 3), (138, 2)], "D", 1158), # Yveltal/Munkidori/Okidogi
    ("latias_psychic",      [(184, 4), (969, 3), (331, 2)], "P", 1125),  # Latias/Scream Tail/Xerneas
    ("koraidon_fighting",   [(979, 4), (447, 3), (117, 2)], "F", 1158),  # Koraidon/Regirock/Cornerstone
    ("mewtwo_rocket",       [(431, 4), (184, 2), (969, 2)], "P", 1088),  # TR Mewtwo/Latias/Scream Tail
    ("terapagos_colorless", [(176, 4), (44, 2), (249, 2)], "W", 1125),   # Terapagos/Ursaluna/Eevee
    ("iron_leaves_grass",   [(75, 4), (198, 3)], "G", 1158),             # Iron Leaves/Durant
    ("volcanion_fire",      [(259, 4), (99, 3), (46, 2)], "R", 1158),    # Volcanion/Ogerpon/Gouging Fire
    ("genesect_metal",      [(547, 4), (993, 3), (299, 2)], "M", 1088),  # Genesect/Orthworm/Hop's Zacian
    ("keldeo_water",        [(583, 4), (369, 3), (179, 2)], "W", 1125),  # Keldeo/Dondozo/Black Kyurem
    ("regirock_fighting",   [(447, 4), (979, 2), (117, 2)], "F", 1158),  # Regirock/Koraidon/Cornerstone
]


def main():
    os.makedirs("gauntlet", exist_ok=True)
    kept, rejected = [], []
    for name, anchors, ekey, ace in SPECS:
        deck = build(anchors, ekey, ace)
        rok, reason = rules_ok(deck)
        if not rok:
            rejected.append((name, "rules:" + reason))
            continue
        if not engine_ok(deck):
            rejected.append((name, "engine-rejected"))
            continue
        path = os.path.join("gauntlet", f"{name}.csv")
        with open(path, "w") as fh:
            fh.write("\n".join(str(x) for x in deck) + "\n")
        kept.append(name)
    print(f"KEPT {len(kept)} legal decks:")
    for n in kept:
        print("  +", n)
    if rejected:
        print(f"REJECTED {len(rejected)}:")
        for n, why in rejected:
            print("  -", n, why)


if __name__ == "__main__":
    main()
