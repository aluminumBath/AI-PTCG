"""Action model.

An ``Action`` is a fully-specified move. The engine's ``legal_actions`` produces
the list of currently-legal actions; agents pick one; ``GameEngine.apply``
mutates state. Keeping actions as small dataclasses (rather than raw ints) makes
the engine debuggable, while ``rl/encoder.py`` maps them to/from a fixed index
space for the neural net.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ActionType(str, Enum):
    PLAY_BASIC = "play_basic"        # bench a Basic Pokémon from hand
    EVOLVE = "evolve"                # evolve a Pokémon in play
    ATTACH_ENERGY = "attach_energy"  # attach 1 energy (once/turn)
    PLAY_ITEM = "play_item"
    PLAY_SUPPORTER = "play_supporter"
    PLAY_STADIUM = "play_stadium"
    ATTACH_TOOL = "attach_tool"
    USE_ABILITY = "use_ability"
    RETREAT = "retreat"
    ATTACK = "attack"
    END_TURN = "end_turn"
    # setup-only
    CHOOSE_ACTIVE = "choose_active"
    PLACE_BENCH = "place_bench"
    SETUP_DONE = "setup_done"


@dataclass(frozen=True)
class Action:
    type: ActionType
    hand_index: Optional[int] = None     # index into hand
    source_uid: Optional[int] = None     # in-play Pokémon performing/receiving
    target_uid: Optional[int] = None     # opponent/own target
    sub_index: Optional[int] = None      # attack index / ability index / bench slot
    extra: tuple = field(default_factory=tuple)  # e.g. energy uids to discard

    def describe(self) -> str:
        bits = [self.type.value]
        for k in ("hand_index", "source_uid", "target_uid", "sub_index"):
            v = getattr(self, k)
            if v is not None:
                bits.append(f"{k}={v}")
        return " ".join(bits)
