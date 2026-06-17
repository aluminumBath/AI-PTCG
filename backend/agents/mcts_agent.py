"""Monte Carlo Tree Search agent (UCT).

This is the "strategic planning" brain. It builds a search tree over future
action sequences, runs heuristic-guided rollouts to terminal (or a depth cap),
and backs up win rates. Because the engine carries hidden information (the
opponent's hand and deck order), this uses *determinized* MCTS: each search
operates on a deep clone of the current state. This is a deliberate, documented
simplification — strong enough to be a serious sparring partner and to seed
AlphaZero-style targets, without a full information-set solver.

It also doubles as the search component the RL trainer can use to generate
high-quality self-play targets (see ``rl/train.py``).
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Optional

from engine.actions import Action, ActionType
from engine.game import GameEngine
from .basic_agents import Agent, HeuristicAgent


@dataclass
class _Node:
    player_to_move: int
    parent: Optional["_Node"] = None
    action_from_parent: Optional[Action] = None
    children: list["_Node"] = field(default_factory=list)
    untried: list[Action] = field(default_factory=list)
    visits: int = 0
    value: float = 0.0  # wins from ROOT player's perspective

    def ucb(self, c: float, root_player: int) -> float:
        if self.visits == 0:
            return float("inf")
        exploit = self.value / self.visits
        explore = c * math.sqrt(math.log(self.parent.visits) / self.visits)
        return exploit + explore


class MCTSAgent(Agent):
    name = "mcts"

    def __init__(
        self,
        iterations: int = 160,
        rollout_depth: int = 40,
        c: float = 1.4,
        rng: Optional[random.Random] = None,
    ):
        self.iterations = iterations
        self.rollout_depth = rollout_depth
        self.c = c
        self.rng = rng or random.Random()
        self._rollout_policy = HeuristicAgent(self.rng)

    def select(self, engine: GameEngine) -> Action:
        root_actions = engine.legal_actions()
        if len(root_actions) == 1:
            return root_actions[0]

        root_player = engine.state.current_player
        root = _Node(player_to_move=root_player, untried=list(root_actions))

        for _ in range(self.iterations):
            sim = engine.clone()
            node = self._tree_policy(root, sim, root_player)
            reward = self._rollout(sim, root_player)
            self._backprop(node, reward)

        # pick the most-visited child (robust choice)
        best = max(root.children, key=lambda n: n.visits, default=None)
        return best.action_from_parent if best else root_actions[0]

    # ------------------------------------------------------------------ #
    def _tree_policy(self, node: _Node, sim: GameEngine, root_player: int) -> _Node:
        while not sim.state.is_over():
            if node.untried:
                action = node.untried.pop(self.rng.randrange(len(node.untried)))
                sim.apply(action)
                child = _Node(
                    player_to_move=sim.state.current_player,
                    parent=node,
                    action_from_parent=action,
                    untried=list(sim.legal_actions()),
                )
                node.children.append(child)
                return child
            if not node.children:
                break
            node = max(node.children, key=lambda n: n.ucb(self.c, root_player))
            sim.apply(node.action_from_parent)
        return node

    def _rollout(self, sim: GameEngine, root_player: int) -> float:
        depth = 0
        while not sim.state.is_over() and depth < self.rollout_depth:
            action = self._rollout_policy.select(sim)
            sim.apply(action)
            depth += 1
        return self._reward(sim, root_player)

    def _reward(self, sim: GameEngine, root_player: int) -> float:
        if sim.state.winner is None:
            # non-terminal: shaped reward via prize differential
            me = sim.state.players[root_player].prizes_taken
            opp = sim.state.players[1 - root_player].prizes_taken
            return 0.5 + 0.5 * max(-1, min(1, (me - opp) / 6.0))
        return 1.0 if sim.state.winner == root_player else 0.0

    def _backprop(self, node: Optional[_Node], reward: float) -> None:
        while node is not None:
            node.visits += 1
            node.value += reward
            node = node.parent
