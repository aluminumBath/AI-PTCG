# Robot Framework tests

End-to-end acceptance tests that exercise the **entire backend API** — health,
auth/authorization, the full game lifecycle (watch, play, save) across every
deck and brain, training metrics, and the card explorer.

## Run

Start the backend (any method — local, Docker, or Render), then:

```bash
pip install -r tests/requirements.txt

# point the tests at your backend (defaults to http://localhost:8000)
export TCG_BASE_URL=http://localhost:8000

robot --outputdir tests/results tests/
```

Open `tests/results/report.html` for the results report and `log.html` for a
step-by-step log.

### Against the Docker stack

```bash
docker compose up --build -d
TCG_BASE_URL=http://localhost:8000 robot --outputdir tests/results tests/
```

## What's covered

| suite                      | focus                                                       |
|----------------------------|-------------------------------------------------------------|
| `01_health_auth.robot`     | health, login (user/email), bad creds, register, duplicate, token identity, admin-only authorization |
| `02_games.robot`           | deck/agent catalogue, AI stepping, play-to-winner, all deck matchups, RL/MCTS turns, human play, illegal-action rejection, save + history, auth on save |
| `03_training_cards.robot`  | training-metrics feed + learning-curve shape, card search/sets + source reporting |

## Extending to the browser UI

These tests target the API surface (the app's functional contract). To add
true browser-level UI tests, install [Browser Library](https://robotframework-browser.org/)
(`pip install robotframework-browser && rfbrowser init`) and drive the running
frontend at `http://localhost:5173` — e.g. log in, start a watch match, assert
the board renders. The API suites above are the fast, deterministic core.
