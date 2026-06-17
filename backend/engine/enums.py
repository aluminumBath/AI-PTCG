"""Core enumerations for the Pokémon TCG engine.

These mirror the official rules vocabulary so the rest of the engine can speak
in domain terms (energy types, status conditions, turn phases) rather than
magic strings.
"""
from __future__ import annotations

from enum import Enum


class EnergyType(str, Enum):
    GRASS = "Grass"
    FIRE = "Fire"
    WATER = "Water"
    LIGHTNING = "Lightning"
    PSYCHIC = "Psychic"
    FIGHTING = "Fighting"
    DARKNESS = "Darkness"
    METAL = "Metal"
    FAIRY = "Fairy"
    DRAGON = "Dragon"
    COLORLESS = "Colorless"  # Colorless cost can be paid by any energy


class CardCategory(str, Enum):
    POKEMON = "Pokemon"
    TRAINER = "Trainer"
    ENERGY = "Energy"


class Stage(str, Enum):
    BASIC = "Basic"
    STAGE_1 = "Stage 1"
    STAGE_2 = "Stage 2"


class TrainerKind(str, Enum):
    ITEM = "Item"
    SUPPORTER = "Supporter"
    STADIUM = "Stadium"
    TOOL = "Tool"


class StatusCondition(str, Enum):
    ASLEEP = "Asleep"
    BURNED = "Burned"
    CONFUSED = "Confused"
    PARALYZED = "Paralyzed"
    POISONED = "Poisoned"


class Phase(str, Enum):
    SETUP = "setup"
    DRAW = "draw"
    MAIN = "main"
    ATTACK = "attack"
    BETWEEN_TURNS = "between_turns"
    GAME_OVER = "game_over"


class Zone(str, Enum):
    DECK = "deck"
    HAND = "hand"
    ACTIVE = "active"
    BENCH = "bench"
    DISCARD = "discard"
    PRIZE = "prize"
    LOST = "lost"  # Lost Zone (cards removed for the game)


# How many prizes the opponent takes when this Pokémon is Knocked Out.
PRIZE_BY_RULE_BOX = {
    None: 1,
    "ex": 2,
    "V": 2,
    "GX": 2,
    "VMAX": 3,
    "VSTAR": 2,
}

BENCH_SIZE = 5
STARTING_HAND = 7
PRIZE_COUNT = 6
DECK_SIZE = 60
MAX_COPIES = 4  # max copies of a card (except basic energy)
