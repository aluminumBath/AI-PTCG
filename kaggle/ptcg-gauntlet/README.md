# PTCG training gauntlet — 57 legal decks + evaluation harness

**57 diverse, rules-legal 60-card decks** for the competition's custom card set,
across **five archetypes**, plus the tooling that built and validated them. Use
them to pressure-test agent and deck changes against a varied field instead of a
single mirror.

## The decks (`decks/*.csv`, 60 bare card-IDs each)

- **15 Basic-ex aggro** — one Basic-ex core per energy type (guaranteed coherent).
- **14 evolution lines** — full Basic -> Stage 1 -> Stage 2 ex (Rare Candy incl.).
- **12 Stage-1 ex** — Basic -> Stage 1 ex (Eeveelutions, Ceruledge, Palafin, ...).
- **9 Mega ex** — Basic -> [Stage 1 ->] Mega ex (Dragonite, Emboar, Lucario, ...).
- **7 non-ex single-prize** — big Basics (N's Zekrom, Reshiram, Tapu Bulu, ...);
  different prize math (opponent takes only 1 prize per KO).

Every deck passed BOTH checks: the construction rules (exactly 60; <=4 copies
except basic energy; <=1 ACE SPEC total; >=1 Basic Pokemon; valid IDs) AND the
real engine (battle_start accepts it — the ultimate arbiter). Evolution lines are
traced automatically via evolvesFrom; energy is derived from each attacker's real
attack cost (so even Dragon lines are playable).

## How to run
The scripts expect the engine and agent next to them. From a copy of the
Simulation bundle (which has main.py, deck.csv, cg/):

    cp -r /path/to/ptcg-gauntlet/decks ./gauntlet
    cp /path/to/ptcg-gauntlet/*.py .
    sed 's/^_USE_SEARCH = True/_USE_SEARCH = False/' main.py > agent_heur.py
    python3 gauntlet_eval.py skill 8    # search vs heuristic, each deck (agent-skill)
    python3 gauntlet_eval.py deck  4    # your deck vs the field (matchup spread)

Rebuild/extend any archetype (add rows to the *_SPECS lists):

    python3 build_gauntlet.py       # 15 Basic-ex aggro
    python3 build_evo_decks.py      # 14 Stage-2 evolution lines
    python3 build_more_decks.py     # 12 Stage-1 ex + 9 Mega ex + 7 non-ex
    python3 make_figures.py         # regenerate writeup figures from measured data

## Results on the shipped agent (for reference)
- Agent skill is **archetype-dependent** — the search's edge concentrates on
  decks with real per-turn tactical choices:
  - **Basic-ex aggro: 70.8%** (85/120), >=50% every deck (the headline number).
  - **non-ex single-prize: ~64%** (tactical Basic aggro).
  - **Stage-1 ex: ~50%**; **Stage-2 evolution: ~42%**; **Mega ex: lower** — all
    setup-heavy, near-forced most turns, so single-turn lookahead has little to
    exploit. A genuine limitation (search horizon), stated plainly.
- **Submission deck** (Mega Abomasnow ex vs the 15 aggro decks): **85.8%**
  (103/17); only even matchups are the two Metal decks — the archetype's soft spot.
- **Robustness:** 380+ crash-free full games incl. search-vs-search. (Very long
  high-HP Mega mirrors can occasionally hit the harness's 4000-selection cap —
  a grindy game, not a crash; Kaggle's own turn limits end such games in play.)

Note: the field is piloted by the weaker heuristic, so absolute rates overstate
performance against equally strong opponents. Treat the spread and the relative
agent-vs-agent gap as the signal, and re-measure after changes.
