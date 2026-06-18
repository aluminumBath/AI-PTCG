"""Card database + sample Standard-format decks.

These cards are hand-authored with faithful structure (HP, energy costs,
weakness, retreat, rule-box prize values, abilities, and attack effects keyed
into the effect registry). The catalogue is intentionally compact — two real
archetypes that play out very differently — and is designed to be *extended*:
add a ``CardDef`` here, implement any new ``effect_id`` in ``engine/effects.py``,
and drop it into a deck list.

Card metadata (names, HP, images) can also be hydrated from the official
pokemontcg.io API via ``data/card_api.py``; this module is the offline,
always-available fallback so the engine never hard-depends on the network.
"""
from __future__ import annotations

from engine.cards import Ability, Attack, CardDef
from engine.enums import (
    CardCategory,
    EnergyType as E,
    Stage,
    TrainerKind,
)

import re as _re
from dataclasses import replace as _replace

CATALOG: dict[str, CardDef] = {}

# Pokémon card ids here are real pokemontcg.io ids (e.g. "sv3-125"), so the card
# art can be served straight from the official image CDN. Only Pokémon appear on
# the board, so only they need art (energy is shown as pips, trainers go to the
# discard). The UI falls back gracefully if an image fails to load.
_IMG_ID = _re.compile(r"^([a-z0-9]+)-([A-Za-z0-9]+)$")


def _card_image(card_id: str) -> str:
    m = _IMG_ID.match(card_id)
    if not m:
        return ""
    return f"https://images.pokemontcg.io/{m.group(1)}/{m.group(2)}.png"


def _reg(card: CardDef) -> CardDef:
    if card.is_pokemon and not card.image:
        url = _card_image(card.id)
        if url:
            card = _replace(card, image=url)
    CATALOG[card.id] = card
    return card


# --------------------------------------------------------------------------- #
# Basic Energy
# --------------------------------------------------------------------------- #
FIRE_ENERGY = _reg(CardDef(
    id="energy-fire", name="Fire Energy", category=CardCategory.ENERGY,
    energy_type=E.FIRE, is_basic_energy=True, provides=(E.FIRE,),
))
PSYCHIC_ENERGY = _reg(CardDef(
    id="energy-psychic", name="Psychic Energy", category=CardCategory.ENERGY,
    energy_type=E.PSYCHIC, is_basic_energy=True, provides=(E.PSYCHIC,),
))
LIGHTNING_ENERGY = _reg(CardDef(
    id="energy-lightning", name="Lightning Energy", category=CardCategory.ENERGY,
    energy_type=E.LIGHTNING, is_basic_energy=True, provides=(E.LIGHTNING,),
))
DARKNESS_ENERGY = _reg(CardDef(
    id="energy-darkness", name="Darkness Energy", category=CardCategory.ENERGY,
    energy_type=E.DARKNESS, is_basic_energy=True, provides=(E.DARKNESS,),
))
WATER_ENERGY = _reg(CardDef(
    id="energy-water", name="Water Energy", category=CardCategory.ENERGY,
    energy_type=E.WATER, is_basic_energy=True, provides=(E.WATER,),
))
GRASS_ENERGY = _reg(CardDef(
    id="energy-grass", name="Grass Energy", category=CardCategory.ENERGY,
    energy_type=E.GRASS, is_basic_energy=True, provides=(E.GRASS,),
))
FIGHTING_ENERGY = _reg(CardDef(
    id="energy-fighting", name="Fighting Energy", category=CardCategory.ENERGY,
    energy_type=E.FIGHTING, is_basic_energy=True, provides=(E.FIGHTING,),
))
METAL_ENERGY = _reg(CardDef(
    id="energy-metal", name="Metal Energy", category=CardCategory.ENERGY,
    energy_type=E.METAL, is_basic_energy=True, provides=(E.METAL,),
))
DOUBLE_TURBO = _reg(CardDef(
    id="energy-double-turbo", name="Double Turbo Energy", category=CardCategory.ENERGY,
    energy_type=E.COLORLESS, is_basic_energy=False, provides=(E.COLORLESS, E.COLORLESS),
    text="Provides 2 Colorless. Attacks do 20 less damage.",
))

# --------------------------------------------------------------------------- #
# Deck 1 — Charizard ex (Fire aggro/midrange)
# --------------------------------------------------------------------------- #
CHARMANDER = _reg(CardDef(
    id="sv3-26", name="Charmander", category=CardCategory.POKEMON,
    hp=70, types=(E.FIRE,), stage=Stage.BASIC,
    weakness=E.WATER, retreat_cost=1,
    attacks=(Attack(name="Heat Tackle", cost=(E.FIRE, E.COLORLESS), damage=30,
                    effect_id="heal_self_30", text="Heals itself 30 (flavor)."),),
))
CHARMELEON = _reg(CardDef(
    id="sv3-27", name="Charmeleon", category=CardCategory.POKEMON,
    hp=90, types=(E.FIRE,), stage=Stage.STAGE_1, evolves_from="Charmander",
    weakness=E.WATER, retreat_cost=2,
    attacks=(Attack(name="Flame Tail", cost=(E.FIRE, E.COLORLESS), damage=60),),
))
CHARIZARD_EX = _reg(CardDef(
    id="sv3-125", name="Charizard ex", category=CardCategory.POKEMON,
    hp=330, types=(E.FIRE,), stage=Stage.STAGE_2, evolves_from="Charmeleon",
    weakness=E.WATER, retreat_cost=2, rule_box="ex",
    abilities=(Ability(name="Infernal Reign", effect_id="ability_accelerate_energy",
                       kind="activated",
                       text="When you evolve into this, attach Fire energy from discard."),),
    attacks=(Attack(name="Burning Darkness", cost=(E.FIRE, E.FIRE),
                    damage=180, effect_id="discard_energy_self_2",
                    text="180+ damage; discard 2 Energy from this Pokémon."),),
))
PIDGEY = _reg(CardDef(
    id="sv3-162", name="Pidgey", category=CardCategory.POKEMON,
    hp=60, types=(E.COLORLESS,), stage=Stage.BASIC,
    weakness=E.LIGHTNING, retreat_cost=1,
    attacks=(Attack(name="Gust", cost=(E.COLORLESS,), damage=10),),
))
PIDGEOT_EX = _reg(CardDef(
    id="sv3-164", name="Pidgeot ex", category=CardCategory.POKEMON,
    hp=280, types=(E.COLORLESS,), stage=Stage.STAGE_1, evolves_from="Pidgey",
    weakness=E.LIGHTNING, retreat_cost=0, rule_box="ex",
    abilities=(Ability(name="Quick Search", effect_id="ability_draw_2",
                       kind="activated", text="Search/refine your hand (simplified: draw 2)."),),
    attacks=(Attack(name="Blustery Wind", cost=(E.COLORLESS, E.COLORLESS),
                    damage=120),),
))

# --------------------------------------------------------------------------- #
# Deck 2 — Gardevoir ex (Psychic toolbox/control)
# --------------------------------------------------------------------------- #
RALTS = _reg(CardDef(
    id="sv1-83", name="Ralts", category=CardCategory.POKEMON,
    hp=70, types=(E.PSYCHIC,), stage=Stage.BASIC,
    weakness=E.METAL, retreat_cost=1,
    attacks=(Attack(name="Confusing Gaze", cost=(E.PSYCHIC,), damage=10,
                    effect_id="sleep_target", text="The Defending Pokémon is now Asleep."),),
))
KIRLIA = _reg(CardDef(
    id="sv1-84", name="Kirlia", category=CardCategory.POKEMON,
    hp=80, types=(E.PSYCHIC,), stage=Stage.STAGE_1, evolves_from="Ralts",
    weakness=E.METAL, retreat_cost=1,
    abilities=(Ability(name="Refinement", effect_id="ability_draw_2", kind="activated",
                       text="Draw cards (simplified: draw 2)."),),
    attacks=(Attack(name="Slap", cost=(E.PSYCHIC,), damage=30),),
))
GARDEVOIR_EX = _reg(CardDef(
    id="sv1-86", name="Gardevoir ex", category=CardCategory.POKEMON,
    hp=310, types=(E.PSYCHIC,), stage=Stage.STAGE_2, evolves_from="Kirlia",
    weakness=E.METAL, retreat_cost=2, rule_box="ex",
    abilities=(Ability(name="Psychic Embrace", effect_id="ability_accelerate_energy",
                       kind="activated",
                       text="Attach Psychic energy from discard to your Pokémon."),),
    attacks=(Attack(name="Miracle Force", cost=(E.PSYCHIC, E.PSYCHIC, E.COLORLESS),
                    damage=190, effect_id="damage_scales_with_energy_30",
                    text="190 + 30 for each extra Energy on this Pokémon."),),
))
DRIFLOON = _reg(CardDef(
    id="sv1-89", name="Drifloon", category=CardCategory.POKEMON,
    hp=70, types=(E.PSYCHIC,), stage=Stage.BASIC,
    weakness=E.DARKNESS, retreat_cost=1,
    attacks=(Attack(name="Fly", cost=(E.PSYCHIC,), damage=20,
                    effect_id="poison_target", text="The Defending Pokémon is Poisoned."),),
))

# --------------------------------------------------------------------------- #
# Trainers (shared toolbox)
# --------------------------------------------------------------------------- #
PROFESSORS_RESEARCH = _reg(CardDef(
    id="trainer-research", name="Professor's Research", category=CardCategory.TRAINER,
    trainer_kind=TrainerKind.SUPPORTER, trainer_effect_id="trainer_professors_research",
    text="Discard your hand and draw 7 cards.",
))
BOSS_ORDERS = _reg(CardDef(
    id="trainer-boss", name="Boss's Orders", category=CardCategory.TRAINER,
    trainer_kind=TrainerKind.SUPPORTER, trainer_effect_id="trainer_boss_orders",
    text="Switch one of your opponent's Benched Pokémon to the Active Spot.",
))
ULTRA_BALL = _reg(CardDef(
    id="trainer-ultraball", name="Ultra Ball", category=CardCategory.TRAINER,
    trainer_kind=TrainerKind.ITEM, trainer_effect_id="trainer_ultra_ball",
    text="Discard 2 cards, then search your deck for a Pokémon.",
))
SWITCH = _reg(CardDef(
    id="trainer-switch", name="Switch", category=CardCategory.TRAINER,
    trainer_kind=TrainerKind.ITEM, trainer_effect_id="trainer_switch",
    text="Switch your Active Pokémon with a Benched Pokémon.",
))
POTION = _reg(CardDef(
    id="trainer-potion", name="Potion", category=CardCategory.TRAINER,
    trainer_kind=TrainerKind.ITEM, trainer_effect_id="trainer_potion_heal_30",
    text="Heal 30 damage from one of your Pokémon.",
))


# --------------------------------------------------------------------------- #
# Deck 3 — Miraidon ex (Lightning basic-aggro)
# --------------------------------------------------------------------------- #
WATTREL = _reg(CardDef(
    id="sv2-81", name="Wattrel", category=CardCategory.POKEMON,
    hp=70, types=(E.LIGHTNING,), stage=Stage.BASIC,
    weakness=E.FIGHTING, retreat_cost=1,
    attacks=(Attack(name="Peck", cost=(E.COLORLESS,), damage=20),),
))
MIRAIDON_EX = _reg(CardDef(
    id="sv1-81", name="Miraidon ex", category=CardCategory.POKEMON,
    hp=220, types=(E.LIGHTNING,), stage=Stage.BASIC,
    weakness=E.FIGHTING, retreat_cost=1, rule_box="ex",
    abilities=(Ability(name="Tandem Unit", effect_id="ability_tandem_unit",
                       kind="activated",
                       text="Search your deck for up to 2 Basic Pokémon and bench them."),),
    attacks=(Attack(name="Photon Blaster", cost=(E.LIGHTNING, E.LIGHTNING, E.COLORLESS),
                    damage=220, effect_id="discard_energy_self_2",
                    text="220 damage. Discard 2 Energy from this Pokémon."),),
))
IRON_HANDS_EX = _reg(CardDef(
    id="sv2-70", name="Iron Hands ex", category=CardCategory.POKEMON,
    hp=230, types=(E.LIGHTNING,), stage=Stage.BASIC,
    weakness=E.FIGHTING, retreat_cost=3, rule_box="ex",
    attacks=(Attack(name="Amp You Very Much", cost=(E.LIGHTNING, E.LIGHTNING, E.COLORLESS),
                    damage=160),),
))

# --------------------------------------------------------------------------- #
# Deck 4 — Roaring Moon ex (Darkness basic-aggro)
# --------------------------------------------------------------------------- #
MURKROW = _reg(CardDef(
    id="sv4-114", name="Murkrow", category=CardCategory.POKEMON,
    hp=70, types=(E.DARKNESS,), stage=Stage.BASIC,
    weakness=E.LIGHTNING, retreat_cost=1,
    attacks=(Attack(name="Nasty Plot", cost=(E.DARKNESS,), damage=20,
                    effect_id="poison_target", text="The Defending Pokémon is Poisoned."),),
))
DARKRAI_EX = _reg(CardDef(
    id="sv4-135", name="Darkrai ex", category=CardCategory.POKEMON,
    hp=220, types=(E.DARKNESS,), stage=Stage.BASIC,
    weakness=E.GRASS, retreat_cost=1, rule_box="ex",
    abilities=(Ability(name="Dark Embrace", effect_id="ability_accelerate_energy",
                       kind="activated",
                       text="Attach a Darkness Energy from discard to a Pokémon."),),
    attacks=(Attack(name="Dark Prism", cost=(E.DARKNESS, E.COLORLESS, E.COLORLESS),
                    damage=120),),
))
ROARING_MOON_EX = _reg(CardDef(
    id="sv4-124", name="Roaring Moon ex", category=CardCategory.POKEMON,
    hp=230, types=(E.DARKNESS,), stage=Stage.BASIC,
    weakness=E.GRASS, retreat_cost=2, rule_box="ex",
    attacks=(Attack(name="Calamity Storm", cost=(E.DARKNESS, E.DARKNESS, E.COLORLESS),
                    damage=200, effect_id="bench_damage_2_all_opp",
                    text="200 damage, and 20 to each of your opponent's Benched Pokémon."),),
))


# --------------------------------------------------------------------------- #
# Deck 5 — Chien-Pao ex (Water energy-acceleration)
# --------------------------------------------------------------------------- #
WIGLETT = _reg(CardDef(
    id="sv2-50", name="Wiglett", category=CardCategory.POKEMON,
    hp=70, types=(E.WATER,), stage=Stage.BASIC,
    weakness=E.GRASS, retreat_cost=1,
    attacks=(Attack(name="Dig", cost=(E.WATER,), damage=20),),
))
CHIEN_PAO_EX = _reg(CardDef(
    id="sv5-61", name="Chien-Pao ex", category=CardCategory.POKEMON,
    hp=220, types=(E.WATER,), stage=Stage.BASIC,
    weakness=E.LIGHTNING, retreat_cost=1, rule_box="ex",
    abilities=(Ability(name="Shivery Chill", effect_id="ability_accelerate_energy",
                       kind="activated",
                       text="Attach a Water Energy from discard to a Pokémon."),),
    attacks=(Attack(name="Hail Blade", cost=(E.WATER, E.WATER),
                    damage=180, effect_id="discard_energy_self_2",
                    text="180 damage. Discard 2 Energy from this Pokémon."),),
))

# --------------------------------------------------------------------------- #
# Deck 6 — Iron Valiant ex (Psychic aggro)
# --------------------------------------------------------------------------- #
NATU = _reg(CardDef(
    id="sv3-71", name="Natu", category=CardCategory.POKEMON,
    hp=60, types=(E.PSYCHIC,), stage=Stage.BASIC,
    weakness=E.DARKNESS, retreat_cost=1,
    attacks=(Attack(name="Peck", cost=(E.PSYCHIC,), damage=20),),
))
IRON_VALIANT_EX = _reg(CardDef(
    id="sv4-89", name="Iron Valiant ex", category=CardCategory.POKEMON,
    hp=220, types=(E.PSYCHIC,), stage=Stage.BASIC,
    weakness=E.METAL, retreat_cost=2, rule_box="ex",
    attacks=(Attack(name="Tachyon Bits", cost=(E.PSYCHIC,), damage=50),
             Attack(name="Laser Blade", cost=(E.PSYCHIC, E.PSYCHIC, E.COLORLESS),
                    damage=180, effect_id="discard_energy_self_2",
                    text="180 damage. Discard 2 Energy from this Pokémon."),),
))


# --------------------------------------------------------------------------- #
# Deck 7 — Ogerpon ex (Grass)
# --------------------------------------------------------------------------- #
TAROUNTULA = _reg(CardDef(
    id="sv1-14", name="Tarountula", category=CardCategory.POKEMON,
    hp=60, types=(E.GRASS,), stage=Stage.BASIC,
    weakness=E.FIRE, retreat_cost=1,
    attacks=(Attack(name="Tackle", cost=(E.GRASS,), damage=10),),
))
OGERPON_EX = _reg(CardDef(
    id="sv6-25", name="Ogerpon ex", category=CardCategory.POKEMON,
    hp=210, types=(E.GRASS,), stage=Stage.BASIC,
    weakness=E.FIRE, retreat_cost=1, rule_box="ex",
    attacks=(Attack(name="Leaf Cut", cost=(E.GRASS, E.COLORLESS), damage=60),
             Attack(name="Bloom Smash", cost=(E.GRASS, E.GRASS, E.COLORLESS),
                    damage=160, effect_id="discard_energy_self_2",
                    text="160 damage. Discard 2 Energy from this Pokémon."),),
))

# --------------------------------------------------------------------------- #
# Deck 8 — Koraidon ex (Fighting, energy acceleration)
# --------------------------------------------------------------------------- #
RIOLU = _reg(CardDef(
    id="sv4-110", name="Riolu", category=CardCategory.POKEMON,
    hp=70, types=(E.FIGHTING,), stage=Stage.BASIC,
    weakness=E.PSYCHIC, retreat_cost=1,
    attacks=(Attack(name="Jab", cost=(E.FIGHTING,), damage=20),),
))
KORAIDON_EX = _reg(CardDef(
    id="sv5-104", name="Koraidon ex", category=CardCategory.POKEMON,
    hp=230, types=(E.FIGHTING,), stage=Stage.BASIC,
    weakness=E.GRASS, retreat_cost=1, rule_box="ex",
    abilities=(Ability(name="Dino Cry", effect_id="ability_accelerate_energy",
                       kind="activated",
                       text="Attach a Fighting Energy from discard to a Pokémon."),),
    attacks=(Attack(name="Wild Impact", cost=(E.FIGHTING, E.FIGHTING, E.COLORLESS),
                    damage=220, effect_id="discard_energy_self_2",
                    text="220 damage. Discard 2 Energy from this Pokémon."),),
))

# --------------------------------------------------------------------------- #
# Deck 9 — Dialga ex (Metal)
# --------------------------------------------------------------------------- #
KLEFKI = _reg(CardDef(
    id="sv1-96", name="Klefki", category=CardCategory.POKEMON,
    hp=70, types=(E.METAL,), stage=Stage.BASIC,
    weakness=E.FIRE, retreat_cost=1,
    attacks=(Attack(name="Spike", cost=(E.METAL,), damage=20),),
))
DIALGA_EX = _reg(CardDef(
    id="sv7-113", name="Dialga ex", category=CardCategory.POKEMON,
    hp=220, types=(E.METAL,), stage=Stage.BASIC,
    weakness=E.FIRE, retreat_cost=2, rule_box="ex",
    attacks=(Attack(name="Metal Blast", cost=(E.METAL, E.METAL), damage=70,
                    effect_id="damage_scales_with_energy_30",
                    text="70 damage plus 30 more for each extra Energy attached."),
             Attack(name="Cosmic Crush", cost=(E.METAL, E.METAL, E.COLORLESS),
                    damage=180, effect_id="discard_energy_self_2",
                    text="180 damage. Discard 2 Energy from this Pokémon."),),
))

# --------------------------------------------------------------------------- #
# Deck 10 — Palkia ex (Water)
# --------------------------------------------------------------------------- #
PALKIA_EX = _reg(CardDef(
    id="sv7-47", name="Palkia ex", category=CardCategory.POKEMON,
    hp=220, types=(E.WATER,), stage=Stage.BASIC,
    weakness=E.LIGHTNING, retreat_cost=2, rule_box="ex",
    attacks=(Attack(name="Subspace Swell", cost=(E.WATER, E.WATER), damage=60,
                    effect_id="damage_scales_with_energy_30",
                    text="60 damage plus 30 more for each extra Energy attached."),
             Attack(name="Spatial Rend", cost=(E.WATER, E.WATER, E.COLORLESS),
                    damage=200, effect_id="discard_energy_self_2",
                    text="200 damage. Discard 2 Energy from this Pokémon."),),
))

# --------------------------------------------------------------------------- #
# Deck 11 — Zeraora ex (Lightning, bench spread)
# --------------------------------------------------------------------------- #
ZERAORA_EX = _reg(CardDef(
    id="sv5-55", name="Zeraora ex", category=CardCategory.POKEMON,
    hp=210, types=(E.LIGHTNING,), stage=Stage.BASIC,
    weakness=E.FIGHTING, retreat_cost=0, rule_box="ex",
    attacks=(Attack(name="Spark Bolt", cost=(E.LIGHTNING,), damage=30),
             Attack(name="Plasma Fists", cost=(E.LIGHTNING, E.LIGHTNING, E.COLORLESS),
                    damage=120, effect_id="bench_damage_2_all_opp",
                    text="120 damage and 20 to each of the opponent's Benched Pokémon."),),
))

# --------------------------------------------------------------------------- #
# Deck 12 — Ho-Oh ex (Fire)
# --------------------------------------------------------------------------- #
FUECOCO = _reg(CardDef(
    id="sv1-36", name="Fuecoco", category=CardCategory.POKEMON,
    hp=70, types=(E.FIRE,), stage=Stage.BASIC,
    weakness=E.WATER, retreat_cost=1,
    attacks=(Attack(name="Ember", cost=(E.FIRE,), damage=20),),
))
HO_OH_EX = _reg(CardDef(
    id="sv3-115", name="Ho-Oh ex", category=CardCategory.POKEMON,
    hp=220, types=(E.FIRE,), stage=Stage.BASIC,
    weakness=E.WATER, retreat_cost=2, rule_box="ex",
    attacks=(Attack(name="Sacred Flame", cost=(E.FIRE, E.COLORLESS), damage=70),
             Attack(name="Rainbow Burn", cost=(E.FIRE, E.FIRE, E.COLORLESS),
                    damage=190, effect_id="discard_energy_self_2",
                    text="190 damage. Discard 2 Energy from this Pokémon."),),
))


# --------------------------------------------------------------------------- #
# Deck 13 — Entei ex (Fire, Burn aggro)
# --------------------------------------------------------------------------- #
ENTEI_EX = _reg(CardDef(
    id="sv7-22", name="Entei ex", category=CardCategory.POKEMON,
    hp=210, types=(E.FIRE,), stage=Stage.BASIC,
    weakness=E.WATER, retreat_cost=2, rule_box="ex",
    attacks=(Attack(name="Searing Flame", cost=(E.FIRE, E.COLORLESS), damage=50,
                    effect_id="burn_target", text="50 damage. The opponent's Active is now Burned."),
             Attack(name="Flare Blitz", cost=(E.FIRE, E.FIRE, E.COLORLESS),
                    damage=170, effect_id="discard_energy_self_2",
                    text="170 damage. Discard 2 Energy from this Pokémon."),),
))

# --------------------------------------------------------------------------- #
# Deck 14 — Pecharunt ex (Psychic, status disruption)
# --------------------------------------------------------------------------- #
PECHARUNT_EX = _reg(CardDef(
    id="sv8-100", name="Pecharunt ex", category=CardCategory.POKEMON,
    hp=200, types=(E.PSYCHIC,), stage=Stage.BASIC,
    weakness=E.DARKNESS, retreat_cost=1, rule_box="ex",
    attacks=(Attack(name="Toxic Chain", cost=(E.PSYCHIC,), damage=30,
                    effect_id="poison_target", text="30 damage. The opponent's Active is now Poisoned."),
             Attack(name="Subjugating Sludge", cost=(E.PSYCHIC, E.PSYCHIC, E.COLORLESS),
                    damage=130, effect_id="sleep_target",
                    text="130 damage. The opponent's Active is now Asleep."),),
))

# --------------------------------------------------------------------------- #
# Deck 15 — Suicune ex (Water, healing control)
# --------------------------------------------------------------------------- #
SUICUNE_EX = _reg(CardDef(
    id="sv8-46", name="Suicune ex", category=CardCategory.POKEMON,
    hp=220, types=(E.WATER,), stage=Stage.BASIC,
    weakness=E.LIGHTNING, retreat_cost=1, rule_box="ex",
    attacks=(Attack(name="Aurora Gain", cost=(E.WATER, E.COLORLESS), damage=60,
                    effect_id="heal_self_30", text="60 damage. Heal 30 from this Pokémon."),
             Attack(name="Hydro Pump", cost=(E.WATER, E.WATER, E.COLORLESS), damage=150),),
))

# --------------------------------------------------------------------------- #
# Deck 16 — Genesect ex (Metal, bench spread)
# --------------------------------------------------------------------------- #
GENESECT_EX = _reg(CardDef(
    id="sv9-120", name="Genesect ex", category=CardCategory.POKEMON,
    hp=210, types=(E.METAL,), stage=Stage.BASIC,
    weakness=E.FIRE, retreat_cost=2, rule_box="ex",
    attacks=(Attack(name="Lock-On Beam", cost=(E.METAL, E.COLORLESS), damage=60),
             Attack(name="Techno Barrage", cost=(E.METAL, E.METAL, E.COLORLESS),
                    damage=110, effect_id="bench_damage_2_all_opp",
                    text="110 damage and 20 to each of the opponent's Benched Pokémon."),),
))

# --------------------------------------------------------------------------- #
# Deck 17 — Lugia ex (Colorless toolbox)
# --------------------------------------------------------------------------- #
BIDOOF = _reg(CardDef(
    id="sv6-114", name="Bidoof", category=CardCategory.POKEMON,
    hp=70, types=(E.COLORLESS,), stage=Stage.BASIC,
    weakness=E.FIGHTING, retreat_cost=1,
    attacks=(Attack(name="Tackle", cost=(E.COLORLESS,), damage=20),),
))
LUGIA_EX = _reg(CardDef(
    id="sv6-139", name="Lugia ex", category=CardCategory.POKEMON,
    hp=220, types=(E.COLORLESS,), stage=Stage.BASIC,
    weakness=E.LIGHTNING, retreat_cost=2, rule_box="ex",
    attacks=(Attack(name="Aeroblast", cost=(E.COLORLESS, E.COLORLESS), damage=70),
             Attack(name="Tempest Dive", cost=(E.COLORLESS, E.COLORLESS, E.COLORLESS),
                    damage=180, effect_id="discard_energy_self_2",
                    text="180 damage. Discard 2 Energy from this Pokémon."),),
))

# --------------------------------------------------------------------------- #
# Deck 18 — Tapu Koko (Lightning, single-prize prize-trade)
# --------------------------------------------------------------------------- #
TAPU_KOKO = _reg(CardDef(
    id="sv10-50", name="Tapu Koko", category=CardCategory.POKEMON,
    hp=120, types=(E.LIGHTNING,), stage=Stage.BASIC,
    weakness=E.FIGHTING, retreat_cost=1,
    attacks=(Attack(name="Spark", cost=(E.LIGHTNING,), damage=20),
             Attack(name="Thunderbolt Dance", cost=(E.LIGHTNING, E.LIGHTNING),
                    damage=90, effect_id="bench_damage_2_all_opp",
                    text="90 damage and 20 to each of the opponent's Benched Pokémon."),),
))


# --------------------------------------------------------------------------- #
# Decks 19-22 — new aces from later sets (sv11 / sv12)
# --------------------------------------------------------------------------- #
FLUTTER_MANE_EX = _reg(CardDef(
    id="sv11-78", name="Flutter Mane ex", category=CardCategory.POKEMON,
    hp=200, types=(E.PSYCHIC,), stage=Stage.BASIC,
    weakness=E.METAL, retreat_cost=1, rule_box="ex",
    attacks=(Attack(name="Midnight Wing", cost=(E.PSYCHIC,), damage=40),
             Attack(name="Phantom Gust", cost=(E.PSYCHIC, E.PSYCHIC), damage=120,
                    effect_id="trainer_boss_orders",
                    text="120 damage. Switch one of the opponent's Benched Pokémon to the Active Spot before this attack."),),
))
RAGING_BOLT_EX = _reg(CardDef(
    id="sv11-123", name="Raging Bolt ex", category=CardCategory.POKEMON,
    hp=220, types=(E.LIGHTNING,), stage=Stage.BASIC,
    weakness=E.FIGHTING, retreat_cost=2, rule_box="ex",
    attacks=(Attack(name="Bellowing Thunder", cost=(E.LIGHTNING, E.LIGHTNING, E.COLORLESS),
                    damage=70, effect_id="damage_scales_with_energy_30",
                    text="70 + 30 for each extra Energy on this Pokémon."),),
))
GHOLDENGO_EX = _reg(CardDef(
    id="sv12-90", name="Gholdengo ex", category=CardCategory.POKEMON,
    hp=220, types=(E.METAL,), stage=Stage.BASIC,
    weakness=E.FIRE, retreat_cost=2, rule_box="ex",
    attacks=(Attack(name="Coin Bonus", cost=(E.METAL, E.COLORLESS), damage=50,
                    effect_id="ability_draw_2", text="50 damage. Draw 2 cards."),
             Attack(name="Make It Rain", cost=(E.METAL, E.METAL, E.COLORLESS),
                    damage=160, effect_id="discard_energy_self_2",
                    text="160 damage. Discard 2 Energy from this Pokémon."),),
))
TERAPAGOS_EX = _reg(CardDef(
    id="sv12-128", name="Terapagos ex", category=CardCategory.POKEMON,
    hp=230, types=(E.COLORLESS,), stage=Stage.BASIC,
    weakness=E.FIGHTING, retreat_cost=3, rule_box="ex",
    attacks=(Attack(name="Crystal Guard", cost=(E.COLORLESS, E.COLORLESS), damage=60,
                    effect_id="heal_self_30", text="60 damage. Heal 30 from this Pokémon."),
             Attack(name="Unified Beatdown", cost=(E.COLORLESS, E.COLORLESS, E.COLORLESS),
                    damage=140),),
))


def _deck(spec: list[tuple[CardDef, int]]) -> list[CardDef]:
    """Build a deck, enforcing the official deck-construction rules:
    exactly 60 cards, and at most 4 copies of any card *except* Basic Energy
    (which is unlimited). Raises if a list is illegal so no rules-breaking deck
    can ship."""
    out: list[CardDef] = []
    for card, n in spec:
        if not card.is_basic_energy and n > 4:
            raise ValueError(
                f"{card.name}: {n} copies exceeds the 4-copy limit "
                "(only Basic Energy is unlimited)."
            )
        out.extend([card] * n)
    if len(out) != 60:
        raise ValueError(f"deck must be 60 cards, got {len(out)}")
    if not any(c.is_basic_pokemon for c in out):
        raise ValueError("deck must contain at least one Basic Pokémon")
    return out


def charizard_deck() -> list[CardDef]:
    return _deck([
        (CHARMANDER, 4), (CHARMELEON, 2), (CHARIZARD_EX, 3),
        (PIDGEY, 3), (PIDGEOT_EX, 2),
        (PROFESSORS_RESEARCH, 4), (BOSS_ORDERS, 3), (ULTRA_BALL, 4),
        (SWITCH, 2), (POTION, 2),
        (FIRE_ENERGY, 27), (DOUBLE_TURBO, 4),
    ])


def gardevoir_deck() -> list[CardDef]:
    return _deck([
        (RALTS, 4), (KIRLIA, 3), (GARDEVOIR_EX, 3),
        (DRIFLOON, 3),
        (PROFESSORS_RESEARCH, 4), (BOSS_ORDERS, 3), (ULTRA_BALL, 4),
        (SWITCH, 2), (POTION, 2),
        (PSYCHIC_ENERGY, 28), (DOUBLE_TURBO, 4),
    ])


def miraidon_deck() -> list[CardDef]:
    return _deck([
        (MIRAIDON_EX, 3), (IRON_HANDS_EX, 2), (WATTREL, 4),
        (PROFESSORS_RESEARCH, 4), (BOSS_ORDERS, 3), (ULTRA_BALL, 4),
        (SWITCH, 2), (POTION, 2),
        (LIGHTNING_ENERGY, 32), (DOUBLE_TURBO, 4),
    ])


def roaring_moon_deck() -> list[CardDef]:
    return _deck([
        (ROARING_MOON_EX, 3), (DARKRAI_EX, 2), (MURKROW, 4),
        (PROFESSORS_RESEARCH, 4), (BOSS_ORDERS, 3), (ULTRA_BALL, 4),
        (SWITCH, 2), (POTION, 2),
        (DARKNESS_ENERGY, 32), (DOUBLE_TURBO, 4),
    ])


def chien_pao_deck() -> list[CardDef]:
    return _deck([
        (CHIEN_PAO_EX, 4), (WIGLETT, 4),
        (PROFESSORS_RESEARCH, 4), (BOSS_ORDERS, 3), (ULTRA_BALL, 4),
        (SWITCH, 2), (POTION, 2),
        (WATER_ENERGY, 33), (DOUBLE_TURBO, 4),
    ])


def iron_valiant_deck() -> list[CardDef]:
    return _deck([
        (IRON_VALIANT_EX, 4), (NATU, 4),
        (PROFESSORS_RESEARCH, 4), (BOSS_ORDERS, 3), (ULTRA_BALL, 4),
        (SWITCH, 2), (POTION, 2),
        (PSYCHIC_ENERGY, 33), (DOUBLE_TURBO, 4),
    ])


def ogerpon_deck() -> list[CardDef]:
    return _deck([
        (OGERPON_EX, 4), (TAROUNTULA, 4),
        (PROFESSORS_RESEARCH, 4), (BOSS_ORDERS, 3), (ULTRA_BALL, 4),
        (SWITCH, 2), (POTION, 2),
        (GRASS_ENERGY, 33), (DOUBLE_TURBO, 4),
    ])


def koraidon_deck() -> list[CardDef]:
    return _deck([
        (KORAIDON_EX, 4), (RIOLU, 4),
        (PROFESSORS_RESEARCH, 4), (BOSS_ORDERS, 3), (ULTRA_BALL, 4),
        (SWITCH, 2), (POTION, 2),
        (FIGHTING_ENERGY, 33), (DOUBLE_TURBO, 4),
    ])


def dialga_deck() -> list[CardDef]:
    return _deck([
        (DIALGA_EX, 4), (KLEFKI, 4),
        (PROFESSORS_RESEARCH, 4), (BOSS_ORDERS, 3), (ULTRA_BALL, 4),
        (SWITCH, 2), (POTION, 2),
        (METAL_ENERGY, 33), (DOUBLE_TURBO, 4),
    ])


def palkia_deck() -> list[CardDef]:
    return _deck([
        (PALKIA_EX, 4), (WIGLETT, 4),
        (PROFESSORS_RESEARCH, 4), (BOSS_ORDERS, 3), (ULTRA_BALL, 4),
        (SWITCH, 2), (POTION, 2),
        (WATER_ENERGY, 33), (DOUBLE_TURBO, 4),
    ])


def zeraora_deck() -> list[CardDef]:
    return _deck([
        (ZERAORA_EX, 4), (WATTREL, 4),
        (PROFESSORS_RESEARCH, 4), (BOSS_ORDERS, 3), (ULTRA_BALL, 4),
        (SWITCH, 2), (POTION, 2),
        (LIGHTNING_ENERGY, 33), (DOUBLE_TURBO, 4),
    ])


def hooh_deck() -> list[CardDef]:
    return _deck([
        (HO_OH_EX, 4), (FUECOCO, 4),
        (PROFESSORS_RESEARCH, 4), (BOSS_ORDERS, 3), (ULTRA_BALL, 4),
        (SWITCH, 2), (POTION, 2),
        (FIRE_ENERGY, 33), (DOUBLE_TURBO, 4),
    ])


def entei_deck() -> list[CardDef]:
    return _deck([
        (ENTEI_EX, 4), (FUECOCO, 4),
        (PROFESSORS_RESEARCH, 4), (BOSS_ORDERS, 3), (ULTRA_BALL, 4),
        (SWITCH, 2), (POTION, 2),
        (FIRE_ENERGY, 33), (DOUBLE_TURBO, 4),
    ])


def pecharunt_deck() -> list[CardDef]:
    return _deck([
        (PECHARUNT_EX, 4), (NATU, 4),
        (PROFESSORS_RESEARCH, 4), (BOSS_ORDERS, 3), (ULTRA_BALL, 4),
        (SWITCH, 2), (POTION, 2),
        (PSYCHIC_ENERGY, 33), (DOUBLE_TURBO, 4),
    ])


def suicune_deck() -> list[CardDef]:
    return _deck([
        (SUICUNE_EX, 4), (WIGLETT, 4),
        (PROFESSORS_RESEARCH, 4), (BOSS_ORDERS, 3), (ULTRA_BALL, 4),
        (SWITCH, 2), (POTION, 2),
        (WATER_ENERGY, 33), (DOUBLE_TURBO, 4),
    ])


def genesect_deck() -> list[CardDef]:
    return _deck([
        (GENESECT_EX, 4), (KLEFKI, 4),
        (PROFESSORS_RESEARCH, 4), (BOSS_ORDERS, 3), (ULTRA_BALL, 4),
        (SWITCH, 2), (POTION, 2),
        (METAL_ENERGY, 33), (DOUBLE_TURBO, 4),
    ])


def lugia_deck() -> list[CardDef]:
    return _deck([
        (LUGIA_EX, 4), (BIDOOF, 4),
        (PROFESSORS_RESEARCH, 4), (BOSS_ORDERS, 3), (ULTRA_BALL, 4),
        (SWITCH, 2), (POTION, 2),
        (WATER_ENERGY, 33), (DOUBLE_TURBO, 4),
    ])


def tapu_koko_deck() -> list[CardDef]:
    # Single-prize: no rule-box attackers, so the opponent must take six KOs.
    return _deck([
        (TAPU_KOKO, 4), (WATTREL, 4),
        (PROFESSORS_RESEARCH, 4), (BOSS_ORDERS, 3), (ULTRA_BALL, 4),
        (SWITCH, 2), (POTION, 2),
        (LIGHTNING_ENERGY, 33), (DOUBLE_TURBO, 4),
    ])


def flutter_mane_deck() -> list[CardDef]:
    return _deck([
        (FLUTTER_MANE_EX, 4), (NATU, 4),
        (PROFESSORS_RESEARCH, 4), (BOSS_ORDERS, 3), (ULTRA_BALL, 4),
        (SWITCH, 2), (POTION, 2),
        (PSYCHIC_ENERGY, 33), (DOUBLE_TURBO, 4),
    ])


def raging_bolt_deck() -> list[CardDef]:
    return _deck([
        (RAGING_BOLT_EX, 4), (WATTREL, 4),
        (PROFESSORS_RESEARCH, 4), (BOSS_ORDERS, 3), (ULTRA_BALL, 4),
        (SWITCH, 2), (POTION, 2),
        (LIGHTNING_ENERGY, 33), (DOUBLE_TURBO, 4),
    ])


def gholdengo_deck() -> list[CardDef]:
    return _deck([
        (GHOLDENGO_EX, 4), (KLEFKI, 4),
        (PROFESSORS_RESEARCH, 4), (BOSS_ORDERS, 3), (ULTRA_BALL, 4),
        (SWITCH, 2), (POTION, 2),
        (METAL_ENERGY, 33), (DOUBLE_TURBO, 4),
    ])


def terapagos_deck() -> list[CardDef]:
    return _deck([
        (TERAPAGOS_EX, 4), (BIDOOF, 4),
        (PROFESSORS_RESEARCH, 4), (BOSS_ORDERS, 3), (ULTRA_BALL, 4),
        (SWITCH, 2), (POTION, 2),
        (WATER_ENERGY, 33), (DOUBLE_TURBO, 4),
    ])


DECKS = {
    "charizard_ex": charizard_deck,
    "gardevoir_ex": gardevoir_deck,
    "miraidon_ex": miraidon_deck,
    "roaring_moon_ex": roaring_moon_deck,
    "chien_pao_ex": chien_pao_deck,
    "iron_valiant_ex": iron_valiant_deck,
    "ogerpon_ex": ogerpon_deck,
    "koraidon_ex": koraidon_deck,
    "dialga_ex": dialga_deck,
    "palkia_ex": palkia_deck,
    "zeraora_ex": zeraora_deck,
    "hooh_ex": hooh_deck,
    "entei_ex": entei_deck,
    "pecharunt_ex": pecharunt_deck,
    "suicune_ex": suicune_deck,
    "genesect_ex": genesect_deck,
    "lugia_ex": lugia_deck,
    "tapu_koko": tapu_koko_deck,
    "flutter_mane_ex": flutter_mane_deck,
    "raging_bolt_ex": raging_bolt_deck,
    "gholdengo_ex": gholdengo_deck,
    "terapagos_ex": terapagos_deck,
}


# --------------------------------------------------------------------------- #
# Set (expansion) names — derived for built-in cards from the id prefix.
# --------------------------------------------------------------------------- #
SETS = {
    "sv1": "Scarlet & Violet Base",
    "sv2": "Paldea Evolved",
    "sv3": "Obsidian Flames",
    "sv4": "Paradox Rift",
    "sv5": "Temporal Forces",
    "sv6": "Twilight Masquerade",
    "sv7": "Stellar Crown",
    "sv8": "Surging Sparks",
    "sv9": "Journey Together",
    "sv10": "Destined Rivals",
    "sv11": "Prismatic Evolutions",
    "sv12": "Twilight Embers",
}


def set_name(card_id: str) -> str:
    code = (card_id or "").split("-")[0]
    return SETS.get(code, "")


def builtin_sets() -> list[dict]:
    """Built-in expansions actually represented in the card pool, with counts."""
    counts: dict[str, int] = {}
    for cd in CATALOG.values():
        code = cd.id.split("-")[0]
        if code in SETS:
            counts[code] = counts.get(code, 0) + 1
    return [{"code": c, "name": SETS[c], "cards": counts[c]}
            for c in SETS if c in counts]


# --------------------------------------------------------------------------- #
# Deck strategy metadata (archetype, type, game plan, key cards).
# --------------------------------------------------------------------------- #
DECK_META = {
    "charizard_ex": {"type": "Fire", "archetype": "Evolution midrange",
        "strategy": "Build Charizard ex behind Pidgeot ex card draw; trade big two-prize attackers and close with energy-accelerated swings.",
        "key_cards": ["Charizard ex", "Pidgeot ex"]},
    "gardevoir_ex": {"type": "Psychic", "archetype": "Evolution midrange",
        "strategy": "Stream attackers with Psychic energy acceleration off the Kirlia/Gardevoir line; grind value and out-resource the opponent.",
        "key_cards": ["Gardevoir ex", "Kirlia"]},
    "miraidon_ex": {"type": "Lightning", "archetype": "All-Basic aggro",
        "strategy": "Explosive turn-one setup; accelerate Lightning energy and apply immediate pressure before the opponent stabilises.",
        "key_cards": ["Miraidon ex", "Iron Hands ex"]},
    "roaring_moon_ex": {"type": "Darkness", "archetype": "All-Basic aggro",
        "strategy": "Hit hard and early with Darkness attackers; use Boss's Orders to target the right Pokémon for prizes.",
        "key_cards": ["Roaring Moon ex", "Darkrai ex"]},
    "chien_pao_ex": {"type": "Water", "archetype": "Energy-acceleration combo",
        "strategy": "Flood the board with Water energy from the discard and swing for huge one-shot numbers.",
        "key_cards": ["Chien-Pao ex"]},
    "iron_valiant_ex": {"type": "Psychic", "archetype": "Aggro tempo",
        "strategy": "Cheap early attacks then a big finisher; punish slow openings with fast Psychic pressure.",
        "key_cards": ["Iron Valiant ex"]},
    "ogerpon_ex": {"type": "Grass", "archetype": "Aggro tempo",
        "strategy": "Low-cost Grass beats and a heavy follow-up; keep tempo against slower evolution decks.",
        "key_cards": ["Ogerpon ex"]},
    "koraidon_ex": {"type": "Fighting", "archetype": "Energy-acceleration aggro",
        "strategy": "Accelerate Fighting energy with Dino Cry and hit 220 quickly; race the opponent down.",
        "key_cards": ["Koraidon ex"]},
    "dialga_ex": {"type": "Metal", "archetype": "Scaling midrange",
        "strategy": "Stack Metal energy so Metal Blast scales, then clean up with a big Cosmic Crush.",
        "key_cards": ["Dialga ex"]},
    "palkia_ex": {"type": "Water", "archetype": "Scaling midrange",
        "strategy": "Grow Subspace Swell with extra Water energy and pivot into a heavy Spatial Rend.",
        "key_cards": ["Palkia ex"]},
    "zeraora_ex": {"type": "Lightning", "archetype": "Bench spread",
        "strategy": "Free retreat for mobility while Plasma Fists chips the whole bench to set up multi-prize turns.",
        "key_cards": ["Zeraora ex"]},
    "hooh_ex": {"type": "Fire", "archetype": "All-Basic aggro",
        "strategy": "Straightforward Fire beatdown with a high-damage finisher.",
        "key_cards": ["Ho-Oh ex"]},
    "entei_ex": {"type": "Fire", "archetype": "Status — Burn",
        "strategy": "Apply Burn for chip damage at every Checkup, then finish with Flare Blitz; pressure plus passive damage.",
        "key_cards": ["Entei ex"]},
    "pecharunt_ex": {"type": "Psychic", "archetype": "Status — disruption",
        "strategy": "Lock the Active with Poison and Sleep so it can't attack or retreat freely, then grind prizes.",
        "key_cards": ["Pecharunt ex"]},
    "suicune_ex": {"type": "Water", "archetype": "Healing control",
        "strategy": "Out-sustain aggro: heal with Aurora Gain and Potion so attackers never quite get the KO.",
        "key_cards": ["Suicune ex"]},
    "genesect_ex": {"type": "Metal", "archetype": "Bench spread",
        "strategy": "Spread damage with Techno Barrage to enable multi-prize Boss's Orders turns.",
        "key_cards": ["Genesect ex"]},
    "lugia_ex": {"type": "Colorless", "archetype": "Colorless toolbox",
        "strategy": "Colorless costs run on any energy, so the deck is consistent and flexible; close with Tempest Dive.",
        "key_cards": ["Lugia ex"]},
    "tapu_koko": {"type": "Lightning", "archetype": "Single-prize tempo",
        "strategy": "Give up only one prize per KO while spreading with Thunderbolt Dance — win the prize trade against two-prize ex decks.",
        "key_cards": ["Tapu Koko"]},
    "flutter_mane_ex": {"type": "Psychic", "archetype": "Aggro + gust",
        "strategy": "Cheap Psychic pressure with a built-in Boss's Orders effect — drag up the Pokémon you want to KO and take prizes on your terms.",
        "key_cards": ["Flutter Mane ex"]},
    "raging_bolt_ex": {"type": "Lightning", "archetype": "Scaling combo",
        "strategy": "Load extra energy so Bellowing Thunder scales, then erase a key threat with one big hit.",
        "key_cards": ["Raging Bolt ex"]},
    "gholdengo_ex": {"type": "Metal", "archetype": "Draw-engine aggro",
        "strategy": "Coin Bonus refills your hand while it attacks; keep the gas flowing and close with Make It Rain.",
        "key_cards": ["Gholdengo ex"]},
    "terapagos_ex": {"type": "Colorless", "archetype": "Tanky control",
        "strategy": "A high-HP Colorless wall that heals as it attacks (Crystal Guard) and runs on any energy — grind the opponent out.",
        "key_cards": ["Terapagos ex"]},
}


# Representative image per deck (its ace card's art); the UI falls back if the
# external image URL 404s, just like individual cards.
def deck_image(deck_id: str) -> str:
    meta = DECK_META.get(deck_id) or {}
    if not meta.get("key_cards"):
        return ""
    ace = meta["key_cards"][0]
    for cd in CATALOG.values():
        if cd.name == ace:
            return cd.image or ""
    return ""


def deck_catalog() -> list[dict]:
    out = []
    for did in DECKS:
        m = DECK_META.get(did, {})
        out.append({"id": did, "type": m.get("type"),
                    "archetype": m.get("archetype"), "strategy": m.get("strategy", ""),
                    "key_cards": m.get("key_cards", []), "image": deck_image(did)})
    return out
