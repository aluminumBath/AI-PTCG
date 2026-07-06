# Kaggle Pokémon TCG AI — project bundle

An end-to-end entry for the TCG Arena / AI-PTCG competition: a working
Simulation-ladder submission, a tuned deck, a validation gauntlet, the Strategy
report, and two honest R&D explorations (multi-turn search, learned value net).

**Start here:** `CHECKPOINT.md` is the single-glance status of everything below.

## What's in each folder
- **`ptcg-sim-submission/`** — the ready-to-upload Simulation entry: schema-correct
  card-aware agent (`main.py`) with bounded forward search + a crash-proof
  heuristic fallback, the 60-card Mega Abomasnow ex deck (`deck.csv`), the engine
  (`cg/`), a README, and `submission.tar.gz`. *Before final upload, swap the
  bundled `cg/` for the official one from the competition Data tab and re-tar* —
  run `swap_engine.py` at the project root (`python3 swap_engine.py /path/to/official/cg`),
  which validates the engine, swaps it in, and rebuilds a flat, game-verified tarball.
- **`STRATEGY_WRITEUP.md`** — the Strategy report (~1.9k words, under the 2k limit),
  with `figures/` (win-rate charts rendered from our own result data).
- **`ptcg-gauntlet/`** — 57 legal decks across 5 archetypes + builders and the
  evaluation harness used to measure the agent and deck.
- **`ptcg-multiturn/`** — experimental multi-turn lookahead (simulates the
  opponent's response) + A/B harness. Honest result: ties single-turn.
- **`ptcg-learned-value/`** — full learned-value pipeline (features → self-play
  data → training → deployable pure-numpy value → agent → A/B). Honest result:
  good win-predictor (AUC 0.78), weaker search heuristic than the hand-tuned eval.
- **`github-pages/`** — a verified-clean git patch + files to deploy the repo's
  frontend to GitHub Pages.

## The short story
Single-turn card-aware search is a strong, crash-free baseline (aggro gauntlet
70.8% search-vs-heuristic; the deck 85.8% across the field). Three ways past it —
deck tuning, multi-turn lookahead, and a one-pass learned value — were each built
and *measured*, and each fails to beat the baseline for an instructive reason. The
measured path forward is iterated on-policy self-play (AlphaZero) with real compute.
Every folder's README documents its own results, caveats, and next levers.
