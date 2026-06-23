# Self-hosting on a Mac (Cloudflare Tunnel + Neon)

Run the whole app from a MacBook and expose it publicly through a Cloudflare
Tunnel, while keeping **Neon Postgres** as the database (unchanged). No Render,
no port-forwarding, no inbound firewall rules, and TLS is handled at Cloudflare's
edge.

```
Browser ──HTTPS──▶ Cloudflare edge ──▶ cloudflared (outbound tunnel) ──▶ Mac
        tcg.yourdomain.com                                   http://127.0.0.1:8000
                                                             FastAPI = API + SPA
                                                                   │
                                                                   └──TLS──▶ Neon Postgres
```

The key simplification: the backend can **serve the built frontend itself**, so
the browser talks to the API *same-origin* and there is no CORS to configure and
only one thing to tunnel.

---

## What changes vs. the Render deploy

| Concern | Render | Mac + Cloudflare Tunnel |
| --- | --- | --- |
| Frontend hosting | static site / nginx container | served by FastAPI (`SERVE_FRONTEND=1`) |
| API base URL | `VITE_API_BASE` → `https://…onrender.com` | **relative** (`window.__API_BASE__ = ""`, already the default) |
| CORS | `*` | irrelevant — same origin |
| TLS / certs | Render-managed | Cloudflare edge (automatic) |
| Public address | `*.onrender.com` | your hostname via the tunnel |
| Process lifecycle | container | `launchd` + `caffeinate` on the Mac |
| DB migrations | `preDeployCommand: alembic upgrade head` | run once in your start script |
| Database | Neon | **Neon (unchanged)** |
| Cold-start screen | needed (free tier sleeps) | harmless (process stays warm) |

The only code change required is the optional SPA-serving block (already in
`backend/api/main.py`, gated on `SERVE_FRONTEND`). Everything else is config.

---

## Prerequisites

```bash
brew install python@3.12 node cloudflared
git clone <your-repo> pokemon-tcg-ai && cd pokemon-tcg-ai
```

You also need a domain on Cloudflare (free plan is fine) and your Neon
connection string.

---

## 1. Environment

Create `backend/.env.sh` (don't commit it) and `source` it from your start
script / `launchd` plist:

```bash
# Database — your Neon string, unchanged. Keep sslmode=require.
export DATABASE_URL="postgresql://USER:PASSWORD@ep-xxxx.neon.tech/neondb?sslmode=require"

# Serve the built frontend from FastAPI (single origin, no CORS).
export SERVE_FRONTEND=1
export PORT=8000

# Optional: the LLM-advised Coach agent.
export ANTHROPIC_API_KEY="sk-ant-..."
export COACH_MODEL="claude-haiku-4-5"
export COACH_TIMEOUT=8

# Optional: where RL checkpoints live (if you train locally).
export CKPT_DIR="$PWD/backend/checkpoints"
```

`DATABASE_URL` is normalized to the psycopg2 driver automatically, so the Neon
string works as-is.

---

## 2. Backend

```bash
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
source .env.sh

# Create/upgrade the schema on Neon (idempotent — includes official-card tables).
alembic upgrade head

# (optional, one-time) load the official card data into Neon, then you can
# delete the CSV/PDF — see README "Official card data".
python ../tools/load_official_data.py --csv ../frontend/public/assets/en_card_data.csv \
                                      --pdf "../frontend/public/assets/Card_ID List_EN.pdf"
```

## 3. Frontend build

```bash
cd ../frontend
npm ci
npm run build          # -> frontend/dist
```

Confirm `frontend/public/config.js` contains `window.__API_BASE__ = "";` (the
default). That makes the SPA call the API relative to its own origin, which is
exactly what we want when FastAPI serves it.

## 4. Run (API + SPA in one process)

```bash
cd ../backend && source .venv/bin/activate && source .env.sh
python -m uvicorn api.main:app --host 127.0.0.1 --port "${PORT:-8000}"
```

Visit `http://localhost:8000` — the app should load, and `http://localhost:8000/api/health`
should return `{"ok": true}`. (FastAPI serves `dist/index.html` and assets;
`/api/*` keeps priority; unknown `/api/*` still returns 404 JSON.)

## 5. Keep it running and awake

macOS sleeps by default — a server must not. Run under `launchd` with
`caffeinate` so it restarts on crash/login and the machine stays awake.

`~/Library/LaunchAgents/com.tcg.backend.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<plist version="1.0"><dict>
  <key>Label</key><string>com.tcg.backend</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/caffeinate</string><string>-dis</string>
    <string>/full/path/pokemon-tcg-ai/backend/.venv/bin/python</string>
    <string>-m</string><string>uvicorn</string><string>api.main:app</string>
    <string>--host</string><string>127.0.0.1</string><string>--port</string><string>8000</string>
  </array>
  <key>WorkingDirectory</key><string>/full/path/pokemon-tcg-ai/backend</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>DATABASE_URL</key><string>postgresql://…neon.tech/neondb?sslmode=require</string>
    <key>SERVE_FRONTEND</key><string>1</string>
    <key>ANTHROPIC_API_KEY</key><string>sk-ant-…</string>
  </dict>
  <key>KeepAlive</key><true/>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>/tmp/tcg-backend.log</string>
  <key>StandardErrorPath</key><string>/tmp/tcg-backend.err</string>
</dict></plist>
```

```bash
launchctl load ~/Library/LaunchAgents/com.tcg.backend.plist
launchctl list | grep com.tcg        # check it's running
```

## 6. Cloudflare Tunnel

**Named tunnel (stable hostname, recommended):**

```bash
cloudflared tunnel login                         # authorize your CF account/domain
cloudflared tunnel create tcg                     # creates creds + a tunnel UUID
cloudflared tunnel route dns tcg tcg.yourdomain.com
```

`~/.cloudflared/config.yml`:

```yaml
tunnel: tcg
credentials-file: /Users/you/.cloudflared/<TUNNEL-UUID>.json
ingress:
  - hostname: tcg.yourdomain.com
    service: http://localhost:8000
  - service: http_status:404
```

Run it (or install as a managed service so it survives reboots):

```bash
cloudflared tunnel run tcg
# or, as a launchd service:
sudo cloudflared service install
```

**Quick tunnel (throwaway URL, no domain needed):**

```bash
cloudflared tunnel --url http://localhost:8000
# prints a temporary https://<random>.trycloudflare.com
```

Open `https://tcg.yourdomain.com` — you're live.

## 7. Security (do this)

- **Change the seeded admin password** (`admin` / `tmppassword`) immediately
  after first login.
- The app already gates everything behind login (Bearer token in
  `localStorage`). For a stronger perimeter, put **Cloudflare Access (Zero
  Trust)** in front of the hostname and restrict to your email(s) — that adds
  SSO *before* any request reaches the Mac, and is free for small teams.
- Consider Cloudflare's WAF / rate-limiting rules on the hostname.
- Keep `.env.sh`, `~/.cloudflared/*.json`, and your Neon string out of git.

## 8. Updating

```bash
git pull
cd frontend && npm ci && npm run build
cd ../backend && source .venv/bin/activate && pip install -r requirements.txt && alembic upgrade head
launchctl kickstart -k gui/$(id -u)/com.tcg.backend     # restart the service
```

## Operational notes

- **Logs:** `/tmp/tcg-backend.log` / `.err` (from the plist), and the cloudflared
  service log.
- **Backups:** Neon manages these; nothing to do locally.
- **In-memory jobs:** tournaments and training episodes live in process memory,
  so they survive as long as the backend runs (no more Render restarts wiping
  them) but are lost if you restart the Mac/service. Persisting them to Postgres
  is a possible follow-up.
- **Apple Silicon GPU:** PyTorch can use the Mac's GPU via Metal (MPS). For the
  learned/search agents below, select the device once:
  ```python
  import torch
  DEVICE = "mps" if torch.backends.mps.is_available() else "cpu"
  ```
  and `.to(DEVICE)` the policy/value network. This is the enabler for the
  heavier agents.

---

## Heavier-duty agents you can now run

Self-hosting removes the constraints that shaped the current roster: there's no
Render free-tier CPU/RAM ceiling, no per-match 10-minute Kaggle limit (that only
applies to the *submitted* Simulation agent, not your local app), the process
stays warm (caches/transposition tables persist), and you have real cores plus
the Apple-Silicon GPU. That makes the following practical. They register exactly
like the existing agents (`backend/agents/registry.py` + a doc in
`model_docs.py`), so they show up everywhere automatically.

### Free wins — deeper budgets on what already exists
The cheapest gain is just turning up the dials, since nothing has to finish in 10
minutes anymore. Add registry entries that reuse current classes with bigger
budgets, e.g.:

```python
"ismcts_deep":  {... "factory": lambda **_: ISMCTSAgent(iterations=4000) ...},
"closer_deep":  {... "factory": lambda **_: ClosingAgent(max_depth=5, budget=8000, trials=6) ...},
"rl_mcts_deep": {... "factory": _rl_mcts_factory(iterations=2000) ...},
```

### 1. AlphaZero-style PUCT (deep MCTS + neural net)
A proper PUCT search that uses the trained policy as a prior and the value head
for leaf evaluation (no random rollouts), running 800–1600 simulations per move
on the GPU. **Implemented** as the `alphazero` agent, plus a self-play trainer
that closes the loop — `rl/alphazero_train.py` records the search's visit-count
distribution as the policy target and the outcome as the value target. Train it
on the GPU to give `alphazero`/`rl_mcts`/`rl` real teeth:

```bash
python -m rl.alphazero_train --iters 40 --games 30 --sims 160 --device mps --eval-games 20
```
**Effort: done — just needs training time.**

### 2. LLM + search hybrid Coach ("propose-and-verify")
The most distinctive option, and the one self-hosting unlocks because it needs
both an API budget and real compute. The LLM (reading card text from the DB)
proposes a handful of candidate *plans*; the engine evaluates each by simulation
(the Closer/minimax/MCTS), and the agent plays the line that actually scores
best — with the LLM's reasoning as the rationale. This mirrors the published
**PokéChamp** "minimax language agent" design. **Effort: medium–high.**

### 3. Deep CFR / regret minimization
Counterfactual Regret Minimization is the gold standard for imperfect-info games
and is almost never applied to a TCG. Deep CFR approximates regrets with a
network trained offline (GPU, hours) to yield a near-Nash, hard-to-exploit
policy. Train as a background job on the Mac; serve the resulting net as an
agent. Very citable for the Strategy writeup. **Effort: high.**

### 4. League / population self-play (AlphaStar-style)
**Implemented** as `--league` in `rl/alphazero_train.py`: the learner trains
against a pool of frozen opponents (the heuristic, optional ISMCTS, and periodic
snapshots of itself), sampled with priority toward opponents that beat it, while
only the learner's moves are recorded. Directly improves robustness and
*consistency across matchups* (a judged axis), and the long run is resumable
(`--resume`):

```bash
python -m rl.alphazero_train --iters 200 --games 30 --sims 160 --device mps \
    --league --league-add-every 10 --eval-games 20 --resume
```
**Effort: done — just needs training time.**

### 5. Neural opponent model → belief-weighted ISMCTS ("deep mind-reader")
**Implemented** as the `neural_ismcts` agent + `rl/opponent_model_train.py`. A
classifier trained on self-play predicts P(each opponent card is in hand) from
public state; ISMCTS then deals the opponent's hand by weighted sampling from
those scores instead of uniformly. Train the model, then the agent uses it
automatically (falling back to uniform ISMCTS if absent):

```bash
python -m rl.opponent_model_train --games 300 --epochs 4 --device mps
```
**Effort: done — just needs training time.**

### 6. Self-consistency / Tree-of-Thought Coach
With a frontier model and a generous per-move timeout, sample N independent
reasonings and majority-vote the action, or let the model expand a small tree of
candidate lines before committing. Stronger and more stable than a single LLM
call, and a nice explainability showcase. **Effort: low–medium.**

### 7. Parallel ensemble of heavy searchers
A real `council` that runs several strong searchers (PUCT, deep ISMCTS, minimax)
*in parallel* across the Mac's cores and combines their votes, instead of the
current sequential, shallow ensemble. **Effort: medium.**

> Practical notes for all of the above: select the MPS device for any network;
> give per-move time/'simulation' budgets rather than the tournament-tuned
> defaults; reuse a persistent transposition table across moves (the warm
> process makes this free); and for training agents (CFR, league, opponent
> model) run them as separate background jobs that emit checkpoints, keeping the
> serving path fast.
