"""Model comparison / tournament engine.

Runs a round-robin between selected agents across a set of decks (the user's
"dataset") and reports a leaderboard plus a head-to-head win matrix, so you can
see which model is the strongest opponent. Sides and deck matchups are alternated
for fairness, and a progress callback supports live UI updates.
"""
from __future__ import annotations

import itertools
import random
from typing import Callable, Optional

from engine.game import GameEngine
from agents.basic_agents import Agent
from agents.registry import make_agent


def play_match(agent_a: Agent, agent_b: Agent, deck_a, deck_b,
               seed: int, max_turns: int = 200, max_steps: int = 20000):
    """Play one game. Returns (winner_seat | None, turns)."""
    eng = GameEngine.new_game(deck_a, deck_b, seed=seed)
    agents = [agent_a, agent_b]
    steps = 0
    while not eng.state.is_over() and eng.state.turn_number <= max_turns and steps < max_steps:
        eng.apply(agents[eng.state.current_player].select(eng))
        steps += 1
    return eng.state.winner, eng.state.turn_number


def run_tournament(
    agent_ids: list[str],
    deck_ids: list[str],
    games_per_pairing: int,
    deck_resolver: Callable[[str], list],
    checkpoint: Optional[str] = None,
    progress: Optional[Callable[[int, int], None]] = None,
    seed: int = 0,
) -> dict:
    agent_ids = list(dict.fromkeys(agent_ids))  # dedupe, keep order
    if len(agent_ids) < 2:
        raise ValueError("Pick at least two models to compare.")
    if not deck_ids:
        raise ValueError("Pick at least one deck.")

    agents = {aid: make_agent(aid, checkpoint) for aid in agent_ids}
    stats = {aid: {"wins": 0, "losses": 0, "draws": 0, "games": 0, "turns": 0}
             for aid in agent_ids}
    matrix = {a: {b: 0 for b in agent_ids} for a in agent_ids}  # row beats col

    pairs = list(itertools.combinations(agent_ids, 2))
    total = len(pairs) * games_per_pairing
    done = 0
    rng = random.Random(seed)

    for a, b in pairs:
        for g in range(games_per_pairing):
            # alternate which model is the first player (turn-1 advantage)
            seat0, seat1 = (a, b) if g % 2 == 0 else (b, a)
            d0 = deck_ids[g % len(deck_ids)]
            d1 = deck_ids[(g + 1) % len(deck_ids)]
            winner, turns = play_match(
                agents[seat0], agents[seat1],
                deck_resolver(d0), deck_resolver(d1),
                seed=rng.randint(0, 2**31 - 1),
            )
            for aid in (seat0, seat1):
                stats[aid]["games"] += 1
                stats[aid]["turns"] += turns
            if winner is None:
                stats[seat0]["draws"] += 1
                stats[seat1]["draws"] += 1
            else:
                win_id = seat0 if winner == 0 else seat1
                lose_id = seat1 if winner == 0 else seat0
                stats[win_id]["wins"] += 1
                stats[lose_id]["losses"] += 1
                matrix[win_id][lose_id] += 1
            done += 1
            if progress:
                progress(done, total)

    standings = []
    for aid in agent_ids:
        s = stats[aid]
        decided = s["wins"] + s["losses"]
        standings.append({
            "agent": aid,
            "wins": s["wins"], "losses": s["losses"], "draws": s["draws"],
            "games": s["games"],
            "winrate": round(s["wins"] / s["games"], 3) if s["games"] else 0.0,
            "winrate_decided": round(s["wins"] / decided, 3) if decided else 0.0,
            "avg_turns": round(s["turns"] / s["games"], 1) if s["games"] else 0.0,
        })
    standings.sort(key=lambda r: (r["winrate"], r["winrate_decided"]), reverse=True)
    return {
        "standings": standings,
        "matrix": matrix,
        "agents": agent_ids,
        "decks": deck_ids,
        "games_per_pairing": games_per_pairing,
        "total_games": total,
        "best": standings[0]["agent"] if standings else None,
    }
