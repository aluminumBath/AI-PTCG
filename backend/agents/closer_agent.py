"""The Closer — a never-miss-lethal wrapper.

Composable: wraps ANY base agent. Before deferring to the base policy, it runs a
bounded search over the *current turn's* reachable action sequences for a line
that wins this turn — a knockout that takes the last prize, or that removes the
opponent's last Pokémon. If a reliable lethal exists it is taken; otherwise the
base agent decides.

Why it matters: missing an available lethal (especially a multi-step one — gust
the right target, attach, then swing) is the single most common failure of
heuristic and search bots under a per-turn time budget. The solver is exhaustive
within its budget and *verifies* any candidate line across several RNG seeds, so
a coin-flip-dependent "lethal" is rejected rather than trusted.
"""
from __future__ import annotations

import random
from typing import Optional

from engine.actions import Action, ActionType
from engine.game import GameEngine
from .basic_agents import Agent, HeuristicAgent

# Search order: terminal attacks first (cheap immediate-lethal check), then the
# development moves most likely to *enable* a lethal, then everything else.
_PRIORITY = {
    ActionType.ATTACK: 0,
    ActionType.CHOOSE_ACTIVE: 1,
    ActionType.USE_ABILITY: 2,
    ActionType.ATTACH_ENERGY: 3,
    ActionType.EVOLVE: 4,
    ActionType.PLAY_ITEM: 5,
    ActionType.PLAY_SUPPORTER: 6,
    ActionType.RETREAT: 7,
    ActionType.PLAY_BASIC: 8,
    ActionType.ATTACH_TOOL: 9,
    ActionType.PLAY_STADIUM: 10,
}


def _ordered(actions: list[Action]) -> list[Action]:
    return sorted(actions, key=lambda a: _PRIORITY.get(a.type, 50))


def find_lethal(engine: GameEngine, me: int, max_depth: int = 3,
                budget: int = 600, trials: int = 3) -> Optional[list[Action]]:
    """Return a sequence of actions that wins for ``me`` *this turn*, or None.

    ``max_depth`` bounds the line length (development steps + the final attack);
    ``budget`` caps the number of simulated actions so the search stays inside a
    per-turn time budget; ``trials`` is how many RNG seeds a candidate must win
    under to be trusted.
    """
    counter = [budget]

    def dfs(eng: GameEngine, depth: int) -> Optional[list[Action]]:
        if counter[0] <= 0 or eng.state.is_over():
            return None
        for a in _ordered(eng.legal_actions()):
            if a.type == ActionType.END_TURN or counter[0] <= 0:
                continue
            child = eng.clone()
            try:
                child.apply(a)
            except Exception:
                continue
            counter[0] -= 1
            if child.state.is_over():
                return [a] if child.state.winner == me else None
            if a.type == ActionType.ATTACK:
                # An attack ends our turn; if it didn't win, the branch is dead.
                continue
            if depth > 1:
                sub = dfs(child, depth - 1)
                if sub is not None:
                    return [a] + sub
        return None

    line = dfs(engine, max_depth)
    if line and _verify(engine, me, line, trials):
        return line
    return None


def _verify(engine: GameEngine, me: int, line: list[Action], trials: int = 4) -> bool:
    """Replay the line under several RNG seeds; require a win every time, so a
    lethal that relies on a coin flip / specific draw is not trusted."""
    for seed in range(trials):
        sim = engine.clone()
        sim.rng = random.Random(9173 + seed)
        ok = True
        for a in line:
            if sim.state.is_over():
                ok = False
                break
            if a not in sim.legal_actions():   # diverged (e.g. a draw moved cards)
                ok = False
                break
            sim.apply(a)
        if not (ok and sim.state.is_over() and sim.state.winner == me):
            return False
    return True


def lethal_plausible(engine: GameEngine, me: int) -> bool:
    """Cheap, *sound* pre-check: can ``me`` possibly win on this turn at all?

    A turn ends the moment you attack, so you get at most one attack. With only
    plain single-target damage you can KO one Pokémon (worth ≤3 prizes). Winning
    therefore requires one of:
      * the opponent down to a single Pokémon (one KO removes their last), or
      * three or fewer of your own prizes left (one big KO can finish), or
      * an effect attack / activated ability in play (which could spread, take
        extra prizes, or KO multiple — so a multi-prize turn is conceivable).
    When none hold, no lethal exists and we can skip the search entirely. This
    makes the Closer nearly free on the early/setup turns that dominate a game.
    """
    s = engine.state
    mine, opp = s.players[me], s.players[1 - me]
    opp_count = (1 if opp.active else 0) + len(opp.bench)
    if opp_count <= 1:
        return True
    if len(mine.prizes) <= 3:
        return True
    for poke in mine.all_pokemon():
        if any(getattr(atk, "effect_id", None) for atk in poke.card.attacks):
            return True
        if any(getattr(ab, "kind", None) == "activated" for ab in poke.card.abilities):
            return True
    return False


class ClosingAgent(Agent):
    """Wrap ``base`` with a guaranteed-lethal check each turn.

    Defaults are tuned for tournament scale: a bounded depth-3 / 600-action
    search (covers attack-now and the common gust/attach → attack lines), gated
    by :func:`lethal_plausible` so most turns cost nothing. Raise ``max_depth`` /
    ``budget`` for deeper single-game analysis.
    """

    name = "closer"

    def __init__(self, base: Optional[Agent] = None, max_depth: int = 3,
                 budget: int = 600, trials: int = 3,
                 rng: Optional[random.Random] = None):
        self.base = base or HeuristicAgent(rng)
        self.max_depth = max_depth
        self.budget = budget
        self.trials = trials
        self.last_explanation = ""

    def select(self, engine: GameEngine) -> Action:
        me = engine.state.current_player
        line = None
        if lethal_plausible(engine, me):
            line = find_lethal(engine, me, self.max_depth, self.budget, self.trials)
        if line:
            steps = " → ".join(a.type.value for a in line)
            self.last_explanation = (
                f"Lethal this turn in {len(line)} step"
                f"{'s' if len(line) > 1 else ''}: {steps}."
            )
            return line[0]
        self.last_explanation = "No guaranteed lethal; deferring to base policy."
        return self.base.select(engine)
