"""Smoke test: run full games to validate the engine end-to-end."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import random
from engine.game import GameEngine
from engine.enums import Phase
from agents.basic_agents import RandomAgent, HeuristicAgent
from data.cards_db import charizard_deck, gardevoir_deck


def play_one(seed: int, agent_a, agent_b, max_turns: int = 200) -> dict:
    eng = GameEngine.new_game(charizard_deck(), gardevoir_deck(),
                              names=("Charizard", "Gardevoir"), seed=seed)
    agents = [agent_a, agent_b]
    steps = 0
    while not eng.state.is_over() and eng.state.turn_number <= max_turns:
        agent = agents[eng.state.current_player]
        action = agent.select(eng)
        eng.apply(action)
        steps += 1
        if steps > 20000:
            break
    return {
        "winner": eng.state.winner,
        "turns": eng.state.turn_number,
        "steps": steps,
        "over": eng.state.is_over(),
        "prizes": [p.prizes_taken for p in eng.state.players],
    }


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    wins = {0: 0, 1: 0, None: 0}
    total_turns = 0
    incomplete = 0
    for i in range(n):
        r = play_one(i, HeuristicAgent(random.Random(i)), RandomAgent(random.Random(1000 + i)))
        wins[r["winner"]] += 1
        total_turns += r["turns"]
        if not r["over"]:
            incomplete += 1
    print(f"Games: {n}")
    print(f"Heuristic (P0) wins: {wins[0]}  Random (P1) wins: {wins[1]}  draws/timeouts: {wins[None]}")
    print(f"Avg turns: {total_turns / n:.1f}   incomplete: {incomplete}")
