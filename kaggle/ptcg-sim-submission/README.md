# PTCG AI Battle Challenge — Simulation submission

**Agent:** a card-aware agent that runs a bounded **forward search** on the
official `cg` engine's own simulator, with a heuristic fallback.

On each MAIN decision it tries every first action, plays the rest of the turn
out with a heuristic rollout, and keeps the action whose end-of-turn board
scores best under a value function (prizes taken, damage dealt, knockout threat,
energy attached, board width). It expands two plies deep before the rollout.
Everything is wrapped so that on any failure it falls back to the pure heuristic
— the search can only ever improve on it, never break it. Offline, fast
(well under the per-turn time budget), and robust (240+ crash-free self-play
games, including search-vs-search).

**Deck:** Mega Abomasnow ex (Water beatdown) — 60 cards, 4-copy legal, 1 ACE SPEC.

## Contents (all at the TOP LEVEL of the archive)
- `main.py`  — the agent entrypoint (`agent(obs_dict) -> list[int]`).
- `deck.csv` — 60 card IDs, one per line (the format the engine reads).
- `cg/`      — the competition game library.

## Rebuild the archive after any edit
From *inside* this folder (so files are top-level, not nested):

    rm -f submission.tar.gz && tar -czvf submission.tar.gz main.py deck.csv cg README.md

Upload `submission.tar.gz` on the Simulation competition page.

## IMPORTANT before final submission
Replace this bundled `cg/` with the **latest official `cg-lib`** from the
competition's Data tab — the organisers may append new enums/fields during the
event, and you want your local engine to match the host exactly. `main.py`
tolerates appended enum members and silently falls back to the heuristic if the
search API is unavailable, but always build against the current library.

**Easiest way** — from the project root, run the helper (it validates the engine
loads, backs up this sample `cg/`, and rebuilds a flat, game-verified tarball):

    python3 swap_engine.py /path/to/official/cg

**Manual way** — replace the `cg/` folder yourself, then, from *inside* this
folder, rebuild the flat archive (the tar must NOT be nested under a wrapper
folder):

    rm -f submission.tar.gz
    tar -czf submission.tar.gz main.py deck.csv cg README.md

Either way, confirm the archive is flat with `tar -tzf submission.tar.gz | head`
(you should see `main.py` and `cg/api.py` at the top level, not
`ptcg-sim-submission/main.py`). The `cg.sample.bak` the helper leaves behind is
just the backup and is not part of the tarball — delete it whenever you like.
