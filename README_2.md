# TCG Arena — Pokémon TCG AI Training Lab

Self-improving AI agents that play the Pokémon Trading Card Game in a real,
rules-faithful environment — plus a polished web app to **watch** agents duel,
**play** against them, and **train** them via reinforcement-learning self-play.

- **Rules engine** — a faithful Standard-format engine: evolution lines, energy
  attachment, abilities, trainers, retreat, status conditions, weakness/
  resistance, prizes (incl. multi-prize `ex` Pokémon), and all win conditions.
- **Four agent brains** — `random`, `heuristic`, `mcts` (Monte-Carlo Tree
  Search planner), and `rl` (a PPO self-play policy/value network).
- **RL self-play** — a PPO trainer with league-style self-play, checkpoints, and
  a live metrics feed for the dashboard.
- **Full-stack app** — FastAPI backend + React/Vite frontend, Postgres-backed
  accounts (login, history, admin), Dockerized locally and deployable to Render
  with a Neon database.

> **Honest scope.** The official API (pokemontcg.io) provides card *data* —
> names, text, images, set legality — but **not executable rules**. Each card's
> behaviour is hand-authored in `backend/engine/effects.py`. The engine ships
> with two deep, faithful Standard archetypes (**Charizard ex** and
> **Gardevoir ex**) and is built to extend: add a card, implement its effect,
> drop it in a deck. The Card Explorer browses the full live card list; the
> battle engine plays the implemented pool.

---

## Architecture

```
backend/
  engine/     rules engine (cards, state, actions, effects, game loop)
  agents/     random, heuristic, MCTS
  rl/         encoder, env, network, PPO trainer, RL agent
  data/       card database + decks, live card-API client
  db/         SQLAlchemy models, session, admin seed
  auth/       bcrypt + JWT auth routes
  api/        FastAPI app (game sessions, training metrics, cards)
frontend/     React/Vite SPA (watch / play / train / cards / admin)
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
**bundled starter checkpoint** (`backend/checkpoints/`). It's only lightly
trained — train it further for stronger play (below).

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
below random, passes random within tens of updates, and approaches/surpasses
the heuristic with hundreds–thousands of updates. A GPU (set nothing special —
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
