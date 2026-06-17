"""Card models.

Two layers:
  * `CardDef` and subclasses are immutable *definitions* (the printed card).
  * `CardInstance` is a concrete copy in a game with mutable state
    (damage, attached energy, status, etc.).

Card *effects* are not stored here as code; they are referenced by an
`effect_id` string and resolved through the effect registry in
``engine/effects.py``. This keeps card data serialisable (it can come straight
from the official API) while keeping executable rules hand-authored and
testable.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Optional

from .enums import (
    CardCategory,
    EnergyType,
    Stage,
    StatusCondition,
    TrainerKind,
)

_counter = itertools.count(1)


@dataclass(frozen=True)
class Attack:
    name: str
    cost: tuple[EnergyType, ...]          # e.g. (FIRE, FIRE, COLORLESS)
    damage: int = 0
    effect_id: Optional[str] = None       # key into the effect registry
    text: str = ""

    @property
    def cost_size(self) -> int:
        return len(self.cost)


@dataclass(frozen=True)
class Ability:
    name: str
    effect_id: str
    text: str = ""
    # "passive" abilities are evaluated continuously; "activated" ones are
    # explicit actions the player can take during their main phase.
    kind: str = "activated"


@dataclass(frozen=True)
class CardDef:
    id: str                  # stable id, e.g. "sv3-125"
    name: str
    category: CardCategory
    set_code: str = ""
    number: str = ""
    image: str = ""

    # --- Pokémon fields ---
    hp: int = 0
    types: tuple[EnergyType, ...] = ()
    stage: Optional[Stage] = None
    evolves_from: Optional[str] = None
    attacks: tuple[Attack, ...] = ()
    abilities: tuple[Ability, ...] = ()
    weakness: Optional[EnergyType] = None
    weakness_mult: int = 2
    resistance: Optional[EnergyType] = None
    resistance_amt: int = 30
    retreat_cost: int = 0
    rule_box: Optional[str] = None   # "ex", "V", "VMAX", ... -> extra prizes

    # --- Trainer fields ---
    trainer_kind: Optional[TrainerKind] = None
    trainer_effect_id: Optional[str] = None

    # --- Energy fields ---
    energy_type: Optional[EnergyType] = None
    is_basic_energy: bool = False
    provides: tuple[EnergyType, ...] = ()   # what energy this card provides

    text: str = ""

    @property
    def is_pokemon(self) -> bool:
        return self.category == CardCategory.POKEMON

    @property
    def is_trainer(self) -> bool:
        return self.category == CardCategory.TRAINER

    @property
    def is_energy(self) -> bool:
        return self.category == CardCategory.ENERGY

    @property
    def is_basic_pokemon(self) -> bool:
        return self.is_pokemon and self.stage == Stage.BASIC


@dataclass
class CardInstance:
    """A concrete card in a game. ``uid`` is unique within a game."""

    card: CardDef
    owner: int
    uid: int = field(default_factory=lambda: next(_counter))

    # --- Pokémon-in-play state ---
    damage: int = 0
    attached_energy: list["CardInstance"] = field(default_factory=list)
    attached_tools: list["CardInstance"] = field(default_factory=list)
    evolved_from: list[CardDef] = field(default_factory=list)  # evolution chain beneath
    status: set[StatusCondition] = field(default_factory=set)
    turn_played: int = -1            # turn it entered play (for evolution timing)
    can_evolve_this_turn: bool = False

    # --- bookkeeping ---
    summoning_sick: bool = True      # just played -> cannot evolve same turn

    @property
    def remaining_hp(self) -> int:
        return self.card.hp - self.damage

    @property
    def is_knocked_out(self) -> bool:
        return self.card.is_pokemon and self.damage >= self.card.hp

    @property
    def prizes_on_ko(self) -> int:
        from .enums import PRIZE_BY_RULE_BOX
        return PRIZE_BY_RULE_BOX.get(self.card.rule_box, 1)

    def energy_count(self) -> int:
        return sum(len(e.card.provides) or 1 for e in self.attached_energy)

    def provided_energy(self) -> list[EnergyType]:
        out: list[EnergyType] = []
        for e in self.attached_energy:
            if e.card.provides:
                out.extend(e.card.provides)
            elif e.card.energy_type:
                out.append(e.card.energy_type)
        return out

    def clone_meta(self) -> dict:
        return {
            "uid": self.uid,
            "name": self.card.name,
            "hp": self.card.hp,
            "damage": self.damage,
            "remaining_hp": self.remaining_hp,
            "energy": [e.card.name for e in self.attached_energy],
            "energy_types": [t.value for t in self.provided_energy()],
            "tools": [t.card.name for t in self.attached_tools],
            "status": sorted(s.value for s in self.status),
            "types": [t.value for t in self.card.types],
            "stage": self.card.stage.value if self.card.stage else None,
            "rule_box": self.card.rule_box,
            "retreat_cost": self.card.retreat_cost,
            "image": self.card.image,
        }
