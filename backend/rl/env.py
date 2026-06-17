"""A light Gym-style wrapper around the engine for self-play RL.

The environment is single-agent from the *learner's* perspective: when it is the
opponent's turn, a fixed opponent policy acts internally until control returns to
the learner or the game ends. This makes PPO collection straightforward while
still training against a real, rules-faithful adversary (which can itself be a
frozen copy of the learner for true self-play).
"""
from __future__ import annotations

import random
from typing import Callable, Optional

import numpy as np

from engine.actions import Action
from engine.game import GameEngine
from data.cards_db import DECKS
from . import encoder


class SelfPlayEnv:
    def __init__(
        self,
        deck_a: str = "charizard_ex",
        deck_b: str = "gardevoir_ex",
        opponent_policy: Optional[Callable[[GameEngine], Action]] = None,
        learner_seat: int = 0,
        seed: Optional[int] = None,
    ):
        self.deck_a = deck_a
        self.deck_b = deck_b
        self.opponent_policy = opponent_policy
        self.learner_seat = learner_seat
        self.rng = random.Random(seed)
        self.engine: Optional[GameEngine] = None

    def set_opponent(self, policy: Callable[[GameEngine], Action]) -> None:
        self.opponent_policy = policy

    def reset(self, seed: Optional[int] = None) -> dict:
        seed = seed if seed is not None else self.rng.randint(0, 2**31 - 1)
        self.engine = GameEngine.new_game(
            DECKS[self.deck_a](), DECKS[self.deck_b](),
            names=(self.deck_a, self.deck_b), seed=seed,
        )
        self._advance_to_learner()
        return self._obs()

    def _advance_to_learner(self) -> None:
        eng = self.engine
        while (
            not eng.state.is_over()
            and eng.state.current_player != self.learner_seat
        ):
            pol = self.opponent_policy
            action = pol(eng) if pol else self.rng.choice(eng.legal_actions())
            eng.apply(action)

    def _obs(self) -> dict:
        eng = self.engine
        actions = eng.legal_actions()
        return {
            "state": encoder.encode_state(eng, self.learner_seat),
            "actions": actions,
            "action_feats": encoder.encode_actions(eng, actions),
            "done": eng.state.is_over(),
        }

    def step(self, action: Action) -> tuple[dict, float, bool, dict]:
        eng = self.engine
        prev_prizes = eng.state.players[self.learner_seat].prizes_taken
        prev_opp_prizes = eng.state.players[1 - self.learner_seat].prizes_taken

        eng.apply(action)
        self._advance_to_learner()

        done = eng.state.is_over()
        reward = 0.0
        # shaped reward: prize swing during the transition
        new_prizes = eng.state.players[self.learner_seat].prizes_taken
        new_opp = eng.state.players[1 - self.learner_seat].prizes_taken
        reward += 0.15 * (new_prizes - prev_prizes)
        reward -= 0.15 * (new_opp - prev_opp_prizes)
        if done:
            if eng.state.winner == self.learner_seat:
                reward += 1.0
            elif eng.state.winner is not None:
                reward -= 1.0
        return self._obs(), reward, done, {"winner": eng.state.winner}
