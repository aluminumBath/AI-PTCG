# TCG Arena — Pokémon TCG AI Training Lab

Self-improving AI agents that play the Pokémon Trading Card Game in a real,
rules-faithful environment — plus a polished web app to **watch** agents duel,
**play** against them, and **train** them via reinforcement-learning self-play.

- **Rules engine** — a faithful Standard-format engine: evolution lines, energy
  attachment, abilities, trainers, retreat, status conditions, weakness/
  resistance, prizes (incl. multi-prize `ex` Pokémon), and all win conditions.
- **Fifteen model types** — `random`, `heuristic`, and three alternative
  heuristic *strategies* (`aggro`, `control`, `setup`); the search family
  `greedy`, `minimax`, `mcts`, `flat_mc`, and `ismcts` (Information-Set MCTS for
  **imperfect information**); the learned `rl` (PPO self-play net) and hybrid
  `rl_mcts`; and three **ensemble / meta** agents that combine the others:
  `council` (every model casts a weighted vote), `prime` (a vote of only the
  strongest models — learned + search + hidden-info + rule-based — guarded by a
  Minimax safety veto), and `meta_top3` (a **dynamic** vote among the current
  top-3 models on the scoreboard, re-resolved whenever the leaderboard changes).
  Spanning baseline, rule-based, search, learned, hybrid, and ensemble families;
  each documented in the **Model scores** explainer modal.
- **Model arena** — run a round-robin between any models across your decks and
  rank them by win rate, with a head-to-head matrix, to find the best opponent.
  Tournaments (and ladder episode runs) execute **server-side as background
  jobs**: they keep running if you switch tabs or refresh — the UI re-attaches
  to the job and shows progress — and a **Stop** button cancels at the next game
  boundary while keeping the partial results.
- **RL self-play** — a PPO trainer with league-style self-play, checkpoints, and
  a live metrics feed for the dashboard.
- **Deck import** — paste a Pokémon TCG Live decklist; it's validated against the
  implemented card pool and becomes selectable in any game.
- **Full-stack app** — FastAPI backend + React/Vite frontend, Postgres-backed
  accounts (login, history, admin), Dockerized locally and deployable to Render
  with a Neon database.

> **Honest scope.** The official API (pokemontcg.io) provides card *data* —
> names, text, images, set legality — but **not executable rules**. Each card's
> behaviour is hand-authored in `backend/engine/effects.py`. The engine ships
> with **twenty-two** faithful, rules-legal Standard archetypes spanning every
> energy type **and a range of strategies** — evolution midrange, all-Basic
> aggro, energy-acceleration combo, scaling midrange, bench spread, status
> disruption (Burn, Poison/Sleep), healing control, a Colorless toolbox, a
> single-prize prize-trade deck, plus draw-engine and tanky-control aces —
> drawn from twelve expansions and each validated as exactly 60 cards under the
> 4-copy rule. The **Decks** tab documents every deck's game plan, key cards and
> ace-card art (`GET /api/decks` · `GET /api/sets`), and the Model arena has a
> 🎲 **Randomize** button to pick a random deck slate for a tournament. Add a
> card, implement its effect, drop it in a deck to extend.

> **Rules & attribution.** The engine enforces the official rules (turn
> structure, the first-player turn-1 restrictions, the Pokémon Checkup for
> Special Conditions on both Actives, weakness/resistance, prizes and win
> conditions, and 60-card / 4-copy deck construction) — see the in-app **Rules
> feed** or `GET /api/rules`. Pokémon and all card/character images are © The
> Pokémon Company / Nintendo / Game Freak / Creatures Inc.; this project claims
> no ownership and shows imagery for reference only (a disclaimer appears above
> any view with images; see `GET /api/sources`).

---

## Architecture

```
backend/
  engine/     rules engine (cards, state, actions, effects, game loop)
  agents/     registry + random, heuristic, minimax, MCTS, RL, RL+MCTS
  eval/       tournament / model-comparison engine
  rl/         encoder, env, network, PPO trainer, RL agent
  data/       card database + decks, deck import, live card-API client
  db/         SQLAlchemy models, session, admin seed
  auth/       bcrypt + JWT auth routes
  api/        FastAPI app (game sessions, tournaments, metrics, cards)
frontend/     React/Vite SPA (watch / play / import / arena / train / cards / admin)
docker-compose.yml   local: postgres + backend + frontend
render.yaml          production blueprint (backend + frontend, Neon DB)
```

---

## Quick start (local, Docker)

Requirements: Docker + Docker Compose.

```bash
docker compose up --build
```

Then open **http://localhost:5173** and sign in with the seeded admin account:

| field    | value                   |
|----------|-------------------------|
| username | `admin`                 |
| email    | `steeleschauer@gmail.com` |
| password | `tmppassword`           |

> ⚠️ **Change the admin password after first login** (it's only a bootstrap
> credential). In production, set `ADMIN_PASSWORD` to something private — the
> password is always stored bcrypt-hashed, never in plaintext.

What's running:
- **db** — Postgres 16 (data persisted in the `pgdata` volume)
- **backend** — FastAPI on `:8000` (auto-creates tables + seeds admin on boot)
- **frontend** — nginx-served app on `:5173`

The "RL policy" agent and the Training dashboard work immediately using the
**bundled checkpoint** (`backend/checkpoints/`), trained for 155 PPO updates
(~2,500 self-play games). On held-out evaluation it wins **~76% vs random** and
**~51% vs the heuristic** — i.e. it has learned, from self-play alone, to play
on par with (slightly ahead of) the hand-crafted baseline. Train it further for
stronger play (below).

---

## Local dev without Docker (optional)

```bash
# backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt           # CPU torch: see note below
export DATABASE_URL="sqlite:///./tcg_dev.db"   # or a Postgres URL
uvicorn api.main:app --reload --port 8000

# frontend (separate terminal)
cd frontend
npm install
echo "VITE_API_BASE=http://localhost:8000" > .env
npm run dev        # http://localhost:5173
```

Without `DATABASE_URL`, the backend falls back to a local SQLite file so it runs
anywhere. For a CPU-only PyTorch install:
`pip install torch --index-url https://download.pytorch.org/whl/cpu`.

---

## Training the RL agent

Training runs **locally** (or on a GPU box). It writes
`backend/checkpoints/policy_latest.pt` and `metrics.json`, which the backend
serves to the "RL policy" agent and the Training dashboard.

```bash
cd backend
# warm up against the heuristic, then graduate to self-play
python -m rl.train --updates 300 --episodes-per-update 16 --opponent heuristic
python -m rl.train --updates 800 --episodes-per-update 24 --opponent self
```

| flag                   | meaning                                              |
|------------------------|------------------------------------------------------|
| `--updates`            | number of PPO updates                                |
| `--episodes-per-update`| self-play games collected per update                 |
| `--opponent`           | `random` \| `heuristic` \| `self` (league self-play) |
| `--selfplay-every`     | snapshot learner as opponent every N updates         |
| `--lr`, `--seed`       | learning rate / RNG seed                             |

**Expectations (honest):** on CPU this is slow but real. The policy starts
below random, passes random within tens of updates, and reaches parity with the
heuristic by ~150 updates (the bundled checkpoint). Continued self-play and more
updates push it further. A GPU (set nothing special —
PyTorch uses CUDA automatically if present) speeds this up dramatically. The
free Render tier **cannot** train; train here and commit the checkpoint, which
the deployed app then serves.

Watch progress live in the **Training lab** tab, or:
```bash
cat backend/checkpoints/metrics.json
```

---

## Deploy to Render + Neon

The blueprint deploys a **backend** (Docker web service) and a **frontend**
(static site). The database is **Neon** (serverless Postgres).

### 1. Create the Neon database
1. Sign up at https://neon.com and create a project (e.g. `tcg`).
2. Copy the **connection string**. It looks like:
   ```
   postgresql://USER:PASSWORD@ep-xxxx.us-east-2.aws.neon.tech/tcg?sslmode=require
   ```
   Keep `?sslmode=require` — Neon requires TLS. (The backend normalises the
   `postgresql://` scheme to the psycopg2 driver automatically.)

### 2. Deploy the blueprint
1. Push this repo to GitHub.
2. In Render: **New → Blueprint**, select the repo. Render reads `render.yaml`
   and creates `tcg-backend` and `tcg-frontend`.
3. On **tcg-backend**, set the environment variables Render marked as required:
   - `DATABASE_URL` → your Neon connection string
   - `ADMIN_PASSWORD` → a private password for the admin account
   - (`JWT_SECRET` is auto-generated; `POKEMONTCG_API_KEY` is optional.)
4. Let the backend deploy, then copy its public URL
   (e.g. `https://tcg-backend.onrender.com`).
5. On **tcg-frontend**, set `VITE_API_BASE` to that backend URL and trigger a
   deploy (a static build bakes the URL in; you can also override at runtime via
   the container's `API_BASE` env when self-hosting the frontend image).

On first boot the backend creates its tables in Neon and seeds the admin user.

> **Free-tier note.** Render free web services sleep when idle and have no GPU,
> so they're for serving (watch/play) and the dashboard — not training. The
> committed checkpoint is what gets served.

---

## Tests

End-to-end [Robot Framework](https://robotframework.org/) acceptance tests
exercise the entire backend API (auth, game lifecycle across every deck and
brain, training metrics, cards). With the backend running:

```bash
pip install -r tests/requirements.txt
TCG_BASE_URL=http://localhost:8000 robot --outputdir tests/results tests/
```

See `tests/README.md` for details and how to extend to browser-level UI tests.

**Continuous integration.** `.github/workflows/ci.yml` runs on every push/PR: it
spins up Postgres, runs the engine smoke test, boots the API, runs the full Robot
suite against it, and builds the frontend. Test reports are uploaded as an
artifact.

## Model scoreboard (lifetime scores)

Every game that involves a model — **Watch**, **Play vs AI**, the **Model
Arena**, and **ladder episodes** — is recorded into a persistent per-model
aggregate (`backend/stats/model_stats.py`, table `model_stats`). The **Model
scores** tab ranks models by win rate and shows games, W/L/D, points
(win = 1, draw = ½) and points-per-game, with one-click **JSON / CSV export**
(`GET /api/models/stats`, `/api/models/stats/export?format=csv`). Report-only
games used to generate the Strategy writeup are excluded so they don't inflate
the lifetime record.

Each row opens a **model explainer** modal — what the model is, *why* it was
chosen, how it works, and a table of its variables with the values used — and
exports that model's manifest in one click (`GET /api/models/{id}/export`), or
all of them at once (`/api/models/export`). Full prose lives in
`backend/agents/model_docs.py` (`GET /api/models/docs`).

If a card's official art is missing or broken, you can paste a replacement URL
right on the card in the **Card explorer**; the override persists
(`POST /api/cards/{id}/image`) and is applied everywhere that card's art shows,
including the battle board.

## Skill-rating ladder (Submissions)

The **Ladder** tab mirrors how Kaggle's simulation competition scores agents.
Enter up to **10 Submissions** (an agent + a deck, or rotating decks). Each one
first plays a **validation game against a copy of itself**; only if it completes
cleanly does it join the pool at μ₀ = 600 (otherwise it's marked **Error** with
logs). Hit **Run episodes** to play rating-matched games on rotating decks.

Skill is a Gaussian **N(μ, σ²)** updated with a from-scratch **TrueSkill-style**
rule (`backend/ladder/rating.py`): the winner's μ rises and the loser's falls (a
draw pulls both toward their mean); the update scales with how surprising the
result was *and* with each agent's uncertainty σ; σ shrinks with the information
gained; and the score/margin never affects ratings. New submissions play more
often for faster feedback, agents are ranked by the conservative score **μ − 3σ**,
and the **rating-progress chart** plots μ over time with a σ band. Each
submission has an **exporter** (model + deck + rating manifest) for the Kaggle
agent seam.

---

## PTCG AI Battle Challenge (Kaggle)

This project targets The Pokémon Company's **Pokémon TCG AI Battle Challenge**,
which has two linked Kaggle categories:

- **Simulation** ([pokemon-tcg-ai-battle](https://www.kaggle.com/competitions/pokemon-tcg-ai-battle)) —
  submit an agent that Kaggle runs in continuous, imperfect-information matches on
  a live leaderboard. Our agent entrypoint lives in
  `backend/competition/agent_entry.py`; the model selection, rules engine, and
  imperfect-information agents are ready — bind its `decode_observation` /
  `encode_action` to the official starter environment to submit.
- **Strategy** ([...-challenge-strategy](https://www.kaggle.com/competitions/pokemon-tcg-ai-battle-challenge-strategy)) —
  the prize-bearing category, judged on the *reasoning* behind your agent. The
  **Competition** tab (or `POST /api/competition/report`) generates a Strategy
  writeup from a live tournament — see `docs/STRATEGY_REPORT.md` for a sample.

For imperfect information we added **ISMCTS**, which re-samples the hidden cards
each search iteration (root-parallel determinization) rather than peeking at the
true state, and the **RL** policy operates only on the observable encoding — both
appropriate for the contest. This repo is unaffiliated with The Pokémon Company
and Kaggle.

---

## Compare models (Model arena)

The **Model arena** tab (or `POST /api/tournament/run`) runs a round-robin
between the models you select, across the decks you select (your "dataset"),
alternating sides and deck matchups for fairness. It returns a ranked
leaderboard (win rate, W/L/D, average game length) and a head-to-head win
matrix, so you can see which model is the strongest opponent. Tournaments run as
a background job — `GET /api/tournament/{job_id}` reports live progress and the
final result. Add a model once in `backend/agents/registry.py` and it shows up
everywhere: the game modes, the arena, and the dropdowns.

---

## Import your own decks

In the app's **Deck import** tab (or `POST /api/decks/import`), paste a decklist
in the Pokémon TCG Live export format — e.g. `3 Charizard ex OBF 125`. The
importer maps each line onto the engine's implemented cards, reports any cards
not yet implemented (so you know why a list isn't battle-ready) and the usual
4-copy guideline, and — when valid — registers the deck so it appears in the
Watch and Play deck pickers. `GET /api/cards/catalog` lists the battle-ready
cards and returns a ready-to-paste sample.

---

## Extending the card pool

1. Add a `CardDef` in `backend/data/cards_db.py` (HP, types, attacks, weakness,
   retreat, `rule_box` for ex/V/VMAX prize counts).
2. If an attack/ability/trainer does something new, implement it in
   `backend/engine/effects.py` under an `@effect("your_key")` and reference that
   key from the card.
3. Add the card to a deck list (or build a new 60-card deck) and register it in
   `DECKS`. The engine, agents, and RL stack pick it up automatically.

---

## API reference (selected)

| method | path                       | notes                         |
|--------|----------------------------|-------------------------------|
| GET    | `/api/health`              | liveness + checkpoint status  |
| POST   | `/api/auth/register`       | `{username,email,password}`   |
| POST   | `/api/auth/login`          | `{username_or_email,password}`|
| GET    | `/api/auth/me`             | current user (Bearer token)   |
| GET    | `/api/decks` `/api/agents` | available decks / brains       |
| POST   | `/api/game/new`            | start watch or play session   |
| POST   | `/api/game/{id}/step`      | advance an AI-vs-AI game       |
| POST   | `/api/game/{id}/action`    | submit a human move            |
| POST   | `/api/game/{id}/save`      | save result (auth)             |
| GET    | `/api/training/metrics`    | learning-curve data            |
| GET    | `/api/cards/search?q=`     | live official card data        |
| GET    | `/api/admin/users`         | admin only                     |

---

## Notes & simplifications

- **MCTS** uses *determinized* search over the true state (it can see hidden
  information during rollouts) — a deliberate, documented simplification that
  makes it a strong sparring partner without a full information-set solver.
- **Setup** (opening hand, active/bench placement) is auto-resolved with a
  sensible rules-legal policy so agents focus on in-game decisions.
- Game sessions are held in memory (fine for a single backend instance).
- Card *data* is live from pokemontcg.io with on-disk caching and an offline
  fallback to the local catalogue; card *rules* are the implemented pool.
