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
ZACIAN = _reg(CardDef(
    id="sv-zac", name="Drifloon", category=CardCategory.POKEMON,
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
        (ZACIAN, 3),
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


DECKS = {
    "charizard_ex": charizard_deck,
    "gardevoir_ex": gardevoir_deck,
    "miraidon_ex": miraidon_deck,
    "roaring_moon_ex": roaring_moon_deck,
    "chien_pao_ex": chien_pao_deck,
    "iron_valiant_ex": iron_valiant_deck,
}
