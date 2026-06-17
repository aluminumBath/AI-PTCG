"""Effect registry.

Card text that *does something* is implemented here as a Python function and
registered under a string key. Card definitions reference effects by that key
(``effect_id`` / ``trainer_effect_id``). This is the seam that lets card *data*
come from the official API while card *behaviour* stays hand-authored, unit
testable, and faithful.

Every effect receives an ``EffectContext`` giving it the engine, the acting
player, the source Pokémon, and any chosen targets. Effects mutate state through
the engine's helper methods so that prize-taking, KO checks, etc. stay
centralised.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, TYPE_CHECKING

from .cards import CardInstance
from .enums import StatusCondition

if TYPE_CHECKING:
    from .game import GameEngine
    from .state import PlayerState


@dataclass
class EffectContext:
    engine: "GameEngine"
    player: "PlayerState"
    opponent: "PlayerState"
    source: Optional[CardInstance] = None
    target: Optional[CardInstance] = None
    base_damage: int = 0


EffectFn = Callable[[EffectContext], None]

_REGISTRY: dict[str, EffectFn] = {}


def effect(key: str):
    def deco(fn: EffectFn) -> EffectFn:
        _REGISTRY[key] = fn
        return fn
    return deco


def get_effect(key: str) -> Optional[EffectFn]:
    return _REGISTRY.get(key)


def has_effect(key: str) -> bool:
    return key in _REGISTRY


# --------------------------------------------------------------------------- #
# Attack effects
# --------------------------------------------------------------------------- #
@effect("burn_target")
def burn_target(ctx: EffectContext) -> None:
    if ctx.target:
        ctx.target.status.add(StatusCondition.BURNED)
        ctx.engine.log(f"{ctx.target.card.name} is now Burned.")


@effect("poison_target")
def poison_target(ctx: EffectContext) -> None:
    if ctx.target:
        ctx.target.status.add(StatusCondition.POISONED)
        ctx.engine.log(f"{ctx.target.card.name} is now Poisoned.")


@effect("paralyze_target")
def paralyze_target(ctx: EffectContext) -> None:
    if ctx.target:
        ctx.target.status.add(StatusCondition.PARALYZED)
        ctx.engine.log(f"{ctx.target.card.name} is Paralyzed.")


@effect("sleep_target")
def sleep_target(ctx: EffectContext) -> None:
    if ctx.target:
        ctx.target.status.add(StatusCondition.ASLEEP)
        ctx.engine.log(f"{ctx.target.card.name} fell Asleep.")


@effect("discard_energy_self_2")
def discard_energy_self_2(ctx: EffectContext) -> None:
    """High-damage attacks that cost you energy (e.g. Charizard ex Burning Darkness)."""
    if ctx.source:
        ctx.engine.discard_energy_from(ctx.source, 2)


@effect("bench_damage_2_all_opp")
def bench_damage_2_all_opp(ctx: EffectContext) -> None:
    """Spread 20 to each Benched Pokémon (the opponent's)."""
    for poke in list(ctx.opponent.bench):
        ctx.engine.deal_raw_damage(poke, 20, ctx.opponent)


@effect("damage_scales_with_energy_30")
def damage_scales_with_energy_30(ctx: EffectContext) -> None:
    """Adds 30 more damage for each extra energy attached (handled in damage calc)."""
    # Implemented in the damage pipeline via attack metadata; left as a marker.
    return


@effect("heal_self_30")
def heal_self_30(ctx: EffectContext) -> None:
    if ctx.source:
        ctx.engine.heal(ctx.source, 30)


# --------------------------------------------------------------------------- #
# Abilities
# --------------------------------------------------------------------------- #
@effect("ability_draw_2")
def ability_draw_2(ctx: EffectContext) -> None:
    """e.g. Pidgeot ex 'Quick Search' simplified: draw to refine hand."""
    ctx.player.draw(2)
    ctx.engine.log(f"{ctx.player.name} used an Ability to draw 2.")


@effect("ability_accelerate_energy")
def ability_accelerate_energy(ctx: EffectContext) -> None:
    """Attach a basic energy from discard to a benched Pokémon (simplified)."""
    energy = next(
        (c for c in ctx.player.discard if c.card.is_energy and c.card.is_basic_energy),
        None,
    )
    target = ctx.player.bench[0] if ctx.player.bench else ctx.player.active
    if energy and target:
        ctx.player.discard.remove(energy)
        target.attached_energy.append(energy)
        ctx.engine.log(
            f"Ability accelerated {energy.card.name} onto {target.card.name}."
        )


@effect("ability_tandem_unit")
def ability_tandem_unit(ctx: EffectContext) -> None:
    """Search the deck for up to 2 Basic Pokémon and put them on the Bench
    (e.g. Miraidon ex 'Tandem Unit'). Powers all-Basic aggro openings."""
    placed = 0
    for card in list(ctx.player.deck):
        if placed >= 2 or not ctx.player.bench_has_space():
            break
        if card.card.is_basic_pokemon:
            ctx.player.deck.remove(card)
            card.turn_played = ctx.engine.state.turn_number
            card.summoning_sick = True
            card.can_evolve_this_turn = False
            ctx.player.bench.append(card)
            placed += 1
    if placed:
        ctx.player.shuffle_deck(ctx.engine.rng)
        ctx.engine.log(f"Tandem Unit benched {placed} Basic Pokémon.")


# --------------------------------------------------------------------------- #
# Trainer effects
# --------------------------------------------------------------------------- #
@effect("trainer_draw_3")
def trainer_draw_3(ctx: EffectContext) -> None:
    ctx.player.draw(3)
    ctx.engine.log(f"{ctx.player.name} drew 3 cards.")


@effect("trainer_professors_research")
def trainer_professors_research(ctx: EffectContext) -> None:
    """Discard your hand, draw 7."""
    while ctx.player.hand:
        ctx.player.discard.append(ctx.player.hand.pop())
    ctx.player.draw(7)
    ctx.engine.log(f"{ctx.player.name} discarded their hand and drew 7.")


@effect("trainer_boss_orders")
def trainer_boss_orders(ctx: EffectContext) -> None:
    """Switch one of the opponent's Benched Pokémon to the Active Spot (gust)."""
    if ctx.opponent.bench and ctx.opponent.active:
        target = ctx.target or ctx.opponent.bench[0]
        if target in ctx.opponent.bench:
            ctx.engine.swap_active(ctx.opponent, target)
            ctx.engine.log(f"Boss's Orders dragged up {target.card.name}.")


@effect("trainer_potion_heal_30")
def trainer_potion_heal_30(ctx: EffectContext) -> None:
    target = ctx.target or ctx.player.active
    if target:
        ctx.engine.heal(target, 30)


@effect("trainer_ultra_ball")
def trainer_ultra_ball(ctx: EffectContext) -> None:
    """Discard 2 cards, search deck for a Pokémon (take the best Basic)."""
    # cost: discard up to 2
    for _ in range(2):
        if ctx.player.hand:
            ctx.player.discard.append(ctx.player.hand.pop())
    poke = max(
        (c for c in ctx.player.deck if c.card.is_pokemon),
        key=lambda c: c.card.hp,
        default=None,
    )
    if poke:
        ctx.player.deck.remove(poke)
        ctx.player.hand.append(poke)
        ctx.engine.log(f"Ultra Ball found {poke.card.name}.")
    ctx.player.shuffle_deck(ctx.engine.rng)


@effect("trainer_switch")
def trainer_switch(ctx: EffectContext) -> None:
    if ctx.player.bench and ctx.player.active:
        target = ctx.target or ctx.player.bench[0]
        if target in ctx.player.bench:
            ctx.engine.swap_active(ctx.player, target)
            ctx.engine.log(f"Switched to {target.card.name}.")
