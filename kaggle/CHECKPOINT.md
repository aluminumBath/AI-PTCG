# AI-PTCG — project checkpoint

Status snapshot of the Kaggle **Pokémon TCG AI Battle Challenge** work. Everything
below is in this outputs folder.

## Competition (verify dates on Kaggle — time-sensitive)
- **Simulation** (live ladder): submissions ~Aug 16; up to 5 agents/day. **You
  must enter this to be eligible for Strategy.**
- **Strategy** (prize-bearing): entry ~Sep 6, writeup ~Sep 13. Judged **Model
  70% / Deck 20% / Report 10%**; writeup ≤2000 words; media gallery must use
  ONLY license-compliant Pokémon Elements. Organizers: pure rule-based agents
  unlikely to score well; "reasonableness standard" on training spend.

## What's built (deliverables)
1. **Simulation submission** — `ptcg-sim-submission/` (`submission.tar.gz`,
   flat: main.py + deck.csv + cg/ + README). A **forward-search agent**: on each
   main decision it expands 2 plies over its own actions on the engine's own
   simulator, rolls the turn out with a heuristic, and scores end-of-turn boards
   (prizes, KO threat, energy, board width). Falls back to a card-aware heuristic
   on any failure → never crashes / never illegal. Deck: **Mega Abomasnow ex**
   (Water aggro), 60-card-legal, 1 ACE SPEC.
2. **Training gauntlet** — `ptcg-gauntlet/` — **57 legal decks** across five archetypes (15 Basic-ex
   aggro, 14 Stage-2 lines, 12 Stage-1 ex, 9 Mega ex, 7 non-ex), each validated vs the rules AND the engine, plus
   builders (`build_gauntlet.py`, `build_evo_decks.py`), the eval harness
   (`gauntlet_eval.py`), and the figure script (`make_figures.py`).
3. **Strategy writeup** — `STRATEGY_WRITEUP.md` (~1576 words) + `figures/`
   (two data charts). Weighted to 70/20/10, grounded in the gauntlet numbers.
4. **GitHub Pages** — `github-pages/` — a verified-clean git patch + raw files
   (workflow + 1-line Vite `base`) and setup steps.
5. **Multi-turn scaffolding** — `ptcg-multiturn/` — experimental agent that looks
   past our turn-end (simulates the opponent's response) with pluggable opponent
   models and a selective trigger, plus an A/B harness. Opponent-model experiment
   is **done and documented**: threat model + selective lookahead is the best
   config but only *ties* single-turn (an initial 66.7% on a small setup sample
   regressed to 50.0% on a larger one). Honest negative result — the framework
   works, but 2-ply lookahead doesn't clear the single-turn baseline. Not in the
   shipped bundle; README lists the levers for future work.
6. **Learned value network** — `ptcg-learned-value/` — full end-to-end pipeline
   (features → self-play data → training → deployable pure-numpy value → agent
   integration → A/B). The value net is a good *win-predictor* (AUC 0.78) but a
   *worse search heuristic* than the hand-tuned `_eval` — loses as a replacement
   (32.8%) and as a blend (~42%). Honest negative result with the AlphaZero-style
   path (iterated on-policy self-play + compute) documented. Not in the bundle.

## Key results (honest)
- Search vs heuristic on the **15 aggro decks: 70.8%** (85/120), ≥50% every deck.
- Search vs heuristic on the **14 evolution decks: ~42%** — within noise of 50%.
  The edge concentrates where per-turn tactical choices exist; setup-heavy
  evolution decks are near-forced most turns, so lookahead barely helps. Genuine
  limitation (single-turn search horizon). A tried eval patch didn't help.
- Abomasnow deck vs the 15 aggro decks: **85.8%** (103/17); soft spot = the two
  Metal decks.
- **380+ crash-free full games** including search-vs-search. The agent now also
  **self-caps a turn** past a high action limit (anti-stall guard, verified to
  fire), so the rare grindy game can't run out the clock — that concern is closed.
- Caveat: the field is piloted by the weaker heuristic, so absolute rates
  overstate performance vs strong opponents. Relative gap + spread are the signal.

## Your remaining actions (things only you can do)
1. **Simulation first** (unlocks Strategy): replace bundled `cg/` with the
   official cg-lib from the competition Data tab, rebuild the tar
   (`rm -f submission.tar.gz && tar -czf submission.tar.gz main.py deck.csv cg README.md`
   from inside the folder), upload. Get on the ladder now.
2. **Deck tuning** (your highest-leverage, 20% of score): playtest the Metal
   matchup; re-run `gauntlet_eval.py deck` after each change.
3. **Pages**: `git apply` the patch, push; deploy the backend (Render, per
   `render.yaml`); set repo Variable `VITE_API_BASE` to the backend URL; set
   Pages source = GitHub Actions.
4. **Strategy**: finalize the writeup voice; build the compliant media gallery.

## Deck tuning (measured this round)
Investigated the Metal soft spot (they one-shot our 350 HP mega through Metal
weakness; we need two hits back). Tested two variants under strong-vs-strong play:
- **+Boss's Orders tempo** — regressed (~38% vs ~46% current): traded a
  consistency card for a situational supporter.
- **Fire splash (Volcanion + Fire energy to hit Metal for weakness)** — cratered
  (~17%): splitting the energy base wrecks Abomasnow's pure-{W}{W}{W} consistency.
Verdict: **keep the current deck.** Metal is a weakness-bound even matchup; no
clean fix exists in the pool without degrading the other 13 matchups. The deck is
already at a good local optimum — deck.csv is unchanged.

## Agent tuning (measured this round)
Three internal improvements were A/B-tested in self-play vs the current agent:
- **Anti-stall turn cap — SHIPPED** (pure robustness, provably invisible in
  normal play; verified to trigger correctly).
- **Speed-aware opening heuristic — dropped** (~50% over 200+ games: no clear gain).
- **Opponent-KO-avoidance eval term — dropped** (~42%: regressed; too defensive
  for aggro's trade-and-race dynamic).
Takeaway: the value function is already well-balanced toward aggression; only the
safety change earned its place. The shipped agent == the validated agent + guard.

## Open ideas if you want to push the agent further
- Learned models (the real path the competition rewards) — **first pipeline built
  and measured** in `ptcg-learned-value/`: a one-pass value net predicts wins well
  (AUC 0.78) but doesn't beat the hand-tuned eval as a search heuristic. Closing
  the gap needs iterated on-policy self-play (AlphaZero loop) + real compute — the
  clear next investment, detailed in that README.
- Train a policy against the engine to replace the rollout (within spend rules);
  drops in behind the same safety fallback.
- Expand the gauntlet further (more evolution lines / dual-type aggro) via the
  builders.
