"""Game state containers."""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional

from .cards import CardDef, CardInstance
from .enums import BENCH_SIZE, Phase, PRIZE_COUNT


@dataclass
class PlayerState:
    index: int
    name: str = "Player"
    deck: list[CardInstance] = field(default_factory=list)
    hand: list[CardInstance] = field(default_factory=list)
    discard: list[CardInstance] = field(default_factory=list)
    lost_zone: list[CardInstance] = field(default_factory=list)
    prizes: list[CardInstance] = field(default_factory=list)
    active: Optional[CardInstance] = None
    bench: list[CardInstance] = field(default_factory=list)

    # per-turn flags
    energy_attached_this_turn: bool = False
    supporter_played_this_turn: bool = False
    retreated_this_turn: bool = False
    stadium_played_this_turn: bool = False
    abilities_used: set[int] = field(default_factory=set)  # uids used this turn

    prizes_taken: int = 0

    def reset_turn_flags(self) -> None:
        self.energy_attached_this_turn = False
        self.supporter_played_this_turn = False
        self.retreated_this_turn = False
        self.stadium_played_this_turn = False
        self.abilities_used = set()

    def all_pokemon(self) -> list[CardInstance]:
        out = []
        if self.active:
            out.append(self.active)
        out.extend(self.bench)
        return out

    def has_pokemon_in_play(self) -> bool:
        return self.active is not None or len(self.bench) > 0

    def bench_has_space(self) -> bool:
        return len(self.bench) < BENCH_SIZE

    def draw(self, n: int = 1) -> list[CardInstance]:
        drawn = []
        for _ in range(n):
            if not self.deck:
                break
            drawn.append(self.deck.pop(0))
        self.hand.extend(drawn)
        return drawn

    def shuffle_deck(self, rng: random.Random) -> None:
        rng.shuffle(self.deck)

    def to_dict(self, hidden: bool = False) -> dict:
        """Serialise. If ``hidden`` is True, opponent-private zones are masked."""
        return {
            "index": self.index,
            "name": self.name,
            "deck_count": len(self.deck),
            "hand": (
                [c.card.name for c in self.hand]
                if not hidden
                else [None] * len(self.hand)
            ),
            "hand_count": len(self.hand),
            "discard": [c.card.name for c in self.discard],
            "discard_count": len(self.discard),
            "lost_count": len(self.lost_zone),
            "prizes_remaining": len(self.prizes),
            "prizes_taken": self.prizes_taken,
            "active": self.active.clone_meta() if self.active else None,
            "bench": [c.clone_meta() for c in self.bench],
            "energy_attached_this_turn": self.energy_attached_this_turn,
            "supporter_played_this_turn": self.supporter_played_this_turn,
        }


@dataclass
class GameState:
    players: list[PlayerState]
    current_player: int = 0
    turn_number: int = 0
    phase: Phase = Phase.SETUP
    stadium: Optional[CardInstance] = None
    stadium_owner: Optional[int] = None
    winner: Optional[int] = None
    log: list[str] = field(default_factory=list)
    rng_seed: int = 0
    first_player: int = 0

    def opponent_of(self, idx: int) -> int:
        return 1 - idx

    @property
    def current(self) -> PlayerState:
        return self.players[self.current_player]

    @property
    def opponent(self) -> PlayerState:
        return self.players[self.opponent_of(self.current_player)]

    def log_event(self, msg: str) -> None:
        self.log.append(f"T{self.turn_number}: {msg}")

    def is_over(self) -> bool:
        return self.phase == Phase.GAME_OVER

    def to_dict(self, viewer: Optional[int] = None) -> dict:
        return {
            "turn_number": self.turn_number,
            "current_player": self.current_player,
            "phase": self.phase.value,
            "winner": self.winner,
            "first_player": self.first_player,
            "stadium": self.stadium.card.name if self.stadium else None,
            "stadium_owner": self.stadium_owner,
            "players": [
                p.to_dict(hidden=(viewer is not None and viewer != p.index))
                for p in self.players
            ],
            "log": self.log[-40:],
        }
