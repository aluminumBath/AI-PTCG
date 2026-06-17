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

CATALOG: dict[str, CardDef] = {}


def _reg(card: CardDef) -> CardDef:
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


def _deck(spec: list[tuple[CardDef, int]]) -> list[CardDef]:
    out: list[CardDef] = []
    for card, n in spec:
        out.extend([card] * n)
    assert len(out) == 60, f"deck must be 60 cards, got {len(out)}"
    return out


def charizard_deck() -> list[CardDef]:
    return _deck([
        (CHARMANDER, 4), (CHARMELEON, 2), (CHARIZARD_EX, 3),
        (PIDGEY, 3), (PIDGEOT_EX, 2),
        (PROFESSORS_RESEARCH, 4), (BOSS_ORDERS, 3), (ULTRA_BALL, 4),
        (SWITCH, 2), (POTION, 2),
        (FIRE_ENERGY, 24), (DOUBLE_TURBO, 7),
    ])


def gardevoir_deck() -> list[CardDef]:
    return _deck([
        (RALTS, 4), (KIRLIA, 3), (GARDEVOIR_EX, 3),
        (ZACIAN, 3),
        (PROFESSORS_RESEARCH, 4), (BOSS_ORDERS, 3), (ULTRA_BALL, 4),
        (SWITCH, 2), (POTION, 2),
        (PSYCHIC_ENERGY, 25), (DOUBLE_TURBO, 7),
    ])


DECKS = {
    "charizard_ex": charizard_deck,
    "gardevoir_ex": gardevoir_deck,
}
