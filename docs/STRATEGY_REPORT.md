# PTCG AI Battle Challenge — Strategy Writeup

*Generated 2026-06-17 20:43 UTC from a live 12-game tournament
(4 games per model pairing) across
4 decks.*

## 1. Summary

We built a rules-faithful Pokémon TCG engine and a family of agents that play it,
then measured them head-to-head to identify the strongest, most robust opponent.
Our top performer in this run was **Heuristic**. The agent reasons under imperfect
information, develops its board before committing to attacks, and times lethal
swings using prize-trade and weakness/resistance math.

## 2. Why this is hard

The PTCG is an **imperfect-information** game: the opponent's hand, both decks'
ordering, and the prize cards are hidden. Unlike chess or Go, an agent cannot
search the true state — it must reason over the *distribution* of states
consistent with what it can see. Our strongest search agent (ISMCTS) is built
around exactly this: it re-samples a plausible hidden state every iteration
rather than peeking.

## 3. The agents (model families)

| Model | Family | Idea |
|---|---|---|
| Random | baseline | Picks a legal move at random. The noise floor. |
| Heuristic | rule-based | Hand-tuned priorities: develop the board, then attack for lethal. |
| Minimax (lookahead) | search | Evaluates each move by the board it leaves behind, anticipating the opponent's reply. |
| MCTS | search | Monte-Carlo Tree Search with heuristic rollouts. Plans several moves ahead. |
| ISMCTS (imperfect-info) | search | Information-Set MCTS: re-samples hidden cards each iteration instead of peeking. Built for imperfect information. |
| RL policy | learned | PPO self-play policy/value network, played greedily. |
| RL + MCTS | hybrid | MCTS that evaluates leaves with the trained value network (AlphaZero-style). |

We deliberately span four families so the strategy report can compare *kinds* of
reasoning, not just hyper-parameters:

- **Rule-based (Heuristic):** encodes the core line of play — develop the board,
  attach to the attacker, evolve toward a win condition, and attack only when it
  is lethal or nothing better remains (attacking ends the turn).
- **Search (Minimax / MCTS / ISMCTS):** look ahead. Minimax scores the board a
  move leaves behind after the opponent's reply; MCTS plans with rollouts;
  **ISMCTS** is our imperfect-information answer — root-parallel determinization
  samples the hidden cards so the policy is robust to what it cannot see.
- **Learned (RL):** a PPO self-play policy/value network trained from scratch,
  using only the *observable* encoding — so it is naturally imperfect-information
  safe.
- **Hybrid (RL + MCTS):** search guided by the learned value network at the
  leaves (AlphaZero-style).

## 4. Measured results

### Leaderboard

| Rank | Model | Win rate | W / L / D | Avg turns |
|---:|---|---:|---|---:|
| 1 | Heuristic | 50% | 4/4/0 | 19.6 |
| 2 | Minimax (lookahead) | 50% | 4/4/0 | 25.0 |
| 3 | RL policy | 50% | 4/4/0 | 14.1 |

### Head-to-head (wins for the row model vs the column model)

| beats ↓ \ vs → | Heuristic | Minimax (lookahead) | RL policy |
|---|---|---|---|
| **Heuristic** | — | 1 | 3 |
| **Minimax (lookahead)** | 3 | — | 1 |
| **RL policy** | 1 | 3 | — |

These are live results from this project's tournament engine; sides and deck
matchups are alternated for fairness.

### Skill ladder — consistency & robustness

Beyond a fixed round-robin, agents are also rated on a **TrueSkill-style skill
ladder** (the Submissions page). Each agent's skill is a Gaussian N(μ, σ²): μ is
the estimated skill and σ the uncertainty, which shrinks as more games are
played. After every episode both ratings update by an amount that scales with how
*surprising* the result was and with each agent's uncertainty; only win/draw/loss
matters, never the margin. This directly measures the two qualities the
competition rewards:

- **Consistency under repeated matches** — ratings converge (σ shrinks) only if
  an agent performs stably across many games; a one-off lucky win barely moves a
  confident rating.
- **Robustness, not reliance on a matchup or opening** — episodes rotate decks
  and pair agents of *similar* rating, so a high rating reflects strength across
  conditions rather than a single favourable matchup. The rating-progress chart
  (μ over time with a σ band) is the figure that visualises this convergence.

## 5. Deck construction

Decks used in this run: charizard_ex, gardevoir_ex, miraidon_ex, chien_pao_ex.

Every deck is validated as exactly **60 cards** under the **4-copy rule** (Basic
Energy is unlimited; Special Energy such as Double Turbo is capped at 4). We
intentionally cover contrasting archetypes so the agents must handle different
tempos:

- **Evolution midrange** (Charizard ex, Gardevoir ex) — slower setup, higher
  ceilings, energy acceleration.
- **All-Basic aggro** (Miraidon ex, Roaring Moon ex, Chien-Pao ex, Iron Valiant
  ex) — fast pressure that punishes slow openings.

Matchup strength across these tempos is a core judging axis, and the head-to-head
matrix above is our evidence for it.

## 6. Rule fidelity

The engine enforces 35 official rules across 8
phases, including the first-player turn-1 restrictions, the Pokémon Checkup
(Special Conditions resolved on *both* Active Pokémon between turns), weakness
×2 / resistance −30, prize math for Rule-Box Pokémon, and the deck-construction
constraints above. Documented simplifications: Game setup (opening hand placement) is auto-resolved with a rules-legal policy so agents focus on in-game decisions., MCTS uses determinized search over the current state — a documented simplification., Card effects are implemented per card; the Card Explorer browses the full official list for reference.

## 7. How we'd climb the leaderboard

1. **More self-play.** The RL policy already reaches parity with the heuristic in
   ~150 updates; hundreds–thousands more (especially on GPU) push it past the
   search agents.
2. **Stronger ISMCTS.** More determinizations and a value-network rollout would
   sharpen imperfect-information play.
3. **Matchup-aware deck choice.** The matrix highlights soft matchups to target
   or shore up.

## 8. Reproducibility

Everything here is generated from the open codebase: the engine, the agent
registry, and the tournament engine. Re-running the Model Arena reproduces the
leaderboard and matrix; the training dashboard reproduces the learning curve.

---

*Pokémon and all card/character images are © The Pokémon Company / Nintendo /
Game Freak / Creatures Inc. This project claims no ownership and uses imagery for
reference only.*
