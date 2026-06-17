"""Observation + action encoding for the RL policy.

Design choice: rather than a brittle global action index (hard in a TCG where
actions reference specific card UIDs), we use a *pointer* formulation. The
network embeds the state once, embeds each currently-legal action, and scores
every legal action against the state. The policy is a softmax over those scores.
This handles variable-sized, state-dependent action sets cleanly and is fully
compatible with PPO.

Everything here is pure numpy so it can be unit-tested without PyTorch.
"""
from __future__ import annotations

import numpy as np

from engine.actions import Action, ActionType
from engine.cards import CardInstance
from engine.enums import EnergyType, StatusCondition
from engine.game import GameEngine

_TYPES = list(EnergyType)
_TYPE_IDX = {t: i for i, t in enumerate(_TYPES)}
_STATUS = list(StatusCondition)
_ACTION_TYPES = list(ActionType)
_ATYPE_IDX = {t: i for i, t in enumerate(_ACTION_TYPES)}

STATE_DIM = 64
ACTION_DIM = 8 + len(_ACTION_TYPES)  # extras + action-type one-hot
MAX_ACTIONS = 80


def _poke_features(poke: CardInstance | None) -> list[float]:
    if poke is None:
        return [0.0] * 8
    hp_frac = poke.remaining_hp / max(1, poke.card.hp)
    type_id = _TYPE_IDX.get(poke.card.types[0], len(_TYPES)) if poke.card.types else len(_TYPES)
    return [
        1.0,
        hp_frac,
        min(1.0, poke.energy_count() / 4.0),
        min(1.0, poke.card.retreat_cost / 4.0),
        1.0 if poke.card.rule_box else 0.0,
        type_id / len(_TYPES),
        1.0 if poke.status else 0.0,
        min(1.0, poke.card.hp / 340.0),
    ]


def encode_state(engine: GameEngine, player: int) -> np.ndarray:
    s = engine.state
    me = s.players[player]
    opp = s.players[1 - player]
    f: list[float] = []
    f.append(min(1.0, s.turn_number / 30.0))
    f.append(1.0 if s.first_player == player else 0.0)
    f.append(len(me.prizes) / 6.0)
    f.append(len(opp.prizes) / 6.0)
    f.append(min(1.0, len(me.hand) / 12.0))
    f.append(min(1.0, len(me.deck) / 60.0))
    f.append(min(1.0, len(me.discard) / 60.0))
    f.append(1.0 if me.energy_attached_this_turn else 0.0)
    f.append(1.0 if me.supporter_played_this_turn else 0.0)
    f.append(1.0 if s.stadium else 0.0)
    f.extend(_poke_features(me.active))
    f.extend(_poke_features(opp.active))
    # bench aggregates
    f.append(len(me.bench) / 5.0)
    f.append(len(opp.bench) / 5.0)
    f.append(np.mean([b.remaining_hp / max(1, b.card.hp) for b in me.bench]) if me.bench else 0.0)
    f.append(sum(b.energy_count() for b in me.bench) / 12.0)
    f.append(1.0 if any(b.card.rule_box for b in me.bench) else 0.0)
    # my active energy by type (how close to attacking)
    type_pool = [0.0] * (len(_TYPES))
    if me.active:
        for e in me.active.provided_energy():
            type_pool[_TYPE_IDX.get(e, len(_TYPES) - 1)] += 1
    f.extend([min(1.0, v / 4.0) for v in type_pool])
    arr = np.asarray(f, dtype=np.float32)
    if arr.shape[0] < STATE_DIM:
        arr = np.concatenate([arr, np.zeros(STATE_DIM - arr.shape[0], dtype=np.float32)])
    return arr[:STATE_DIM]


def encode_action(engine: GameEngine, action: Action) -> np.ndarray:
    s = engine.state
    me = s.current
    extras = [0.0] * 8
    # extras[0]: normalized attack damage, extras[1]: lethal flag
    if action.type == ActionType.ATTACK and me.active and s.opponent.active:
        atk = me.active.card.attacks[action.sub_index]
        dmg = engine._compute_damage(me.active, s.opponent.active, atk)
        extras[0] = min(1.0, dmg / 340.0)
        extras[1] = 1.0 if dmg >= s.opponent.active.remaining_hp else 0.0
    if action.type == ActionType.EVOLVE:
        extras[2] = 1.0
    if action.type == ActionType.ATTACH_ENERGY:
        extras[3] = 1.0
        if me.active and action.target_uid == me.active.uid:
            extras[4] = 1.0
    if action.type in (ActionType.PLAY_SUPPORTER, ActionType.PLAY_ITEM):
        extras[5] = 1.0
    if action.type == ActionType.USE_ABILITY:
        extras[6] = 1.0
    if action.type == ActionType.RETREAT:
        extras[7] = 1.0
    onehot = [0.0] * len(_ACTION_TYPES)
    onehot[_ATYPE_IDX[action.type]] = 1.0
    return np.asarray(extras + onehot, dtype=np.float32)


def encode_actions(engine: GameEngine, actions: list[Action]) -> np.ndarray:
    if not actions:
        return np.zeros((0, ACTION_DIM), dtype=np.float32)
    return np.stack([encode_action(engine, a) for a in actions])
