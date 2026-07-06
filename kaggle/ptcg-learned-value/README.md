# Learned value network — end-to-end pipeline + honest result

The shipped agent scores boards with a hand-tuned `_eval` (a hand-weighted linear
combination of prize/HP/threat/board signals). The natural "learned" version keeps
the same signals but lets the **weights be learned from self-play outcomes**. This
folder is that pipeline, end to end: feature extraction → self-play data → training
→ a deployable pure-numpy value → agent integration → measurement.

**Headline result (honest):** the value net is a good *win-predictor* (AUC 0.78)
but a *worse search heuristic* than the hand-tuned `_eval` — it loses whether it
**replaces** the eval (32.8%) or **augments** it (≈42–44%). This is a well-known
result in game AI, with a clear cause and a clear path forward (below). The
pipeline works and is the right foundation; a one-pass value net is not enough to
beat a well-tuned heuristic. **Not recommended for the shipped submission** — it's
an R&D deliverable. The shipped `main.py` is unchanged.

## Why linear
`_eval` is already a hand-weighted **linear** function of board signals, so the
honest learned counterpart is a **logistic-regression** value net over the same
signals. Keeping it linear means inference is a single dot product
(`value_net.value`), so the trained value drops into the agent as **pure numpy —
no sklearn at inference**, i.e. it is competition-deployable.

## Files
- `value_net.py` — `features(state, me)` (29 board signals, shared by training and
  inference) + `value(weights, state, me)` (pure-numpy P(win)).
- `gen_data.py` — heuristic self-play across a deck spread; records every MAIN
  decision's features labelled with the game's outcome; splits by game. → `data.npz`
- `train_value.py` — trains the logistic value net (+ an MLP for comparison),
  reports val accuracy / log-loss / AUC, prints learned weights, exports
  `weights.json`.
- `agent_value.py` — the shipped agent with `_eval` able to use the learned value
  (`_BLEND == 0`) or augment the hand eval with it (`_BLEND > 0`); `_LEARNED_W =
  None` recovers the exact hand-tuned baseline.
- `weights.json` — the trained linear value net (mean/scale/coef/intercept).

## How to run
From a copy of the Simulation bundle that also has `main.py`, `cg/`, a `gauntlet/`
folder, and these files (they `import main` for the card DB + damage helpers):

    python3 gen_data.py 150 data.npz        # ~150 self-play games -> dataset
    python3 train_value.py data.npz weights.json
    # then A/B agent_value (learned) vs agent_value with _LEARNED_W=None (hand eval)

## Measured results
Training (150 games, 9269 positions, split by game):

| model | val acc | log-loss | AUC |
|---|---|---|---|
| **logistic (deployed)** | 0.698 | 0.560 | **0.781** |
| MLP (32,16) | 0.645 | 1.834 | 0.699 |
| coin flip | 0.500 | 0.693 | 0.500 |

Inside the search, vs the hand-tuned `_eval` (self-play, mirror matches):

| value used in search | result vs hand-tuned |
|---|---|
| **learned, replacing `_eval`** | 32.8% (loses) |
| learned, blended (weight 800) | 44.4% (loses) |
| learned, blended (weight 2000) | 41.7% (loses, worse) |

So the value net predicts winners well but does not rank the search's candidate
lines as well as the hand-tuned eval — and blending it in only drags the eval down.

## Why a good predictor is a worse search heuristic
1. **Distribution shift.** The value was trained on states from *heuristic*
   self-play, but the search evaluates counterfactual end-of-turn boards it is
   considering — many off the heuristic's distribution. The net is globally
   accurate yet misranks those specific candidates.
2. **Objective mismatch.** Log-loss on "who eventually won" is not the same as
   "which of these five boards gives the best continuation." The hand eval was
   tuned (by measurement) specifically for that move-ordering job.
3. **One pass isn't enough.** Beating a well-tuned heuristic with a learned value
   is exactly what AlphaZero-style **iterated on-policy self-play** is for: search
   generates data → train value → search with the new value → repeat. One
   supervised pass on heuristic data can't close that gap.

## The path forward (what a serious entry would do)
- **On-policy, iterated self-play**: generate data with the *search* agent (not the
  heuristic) and iterate value ↔ search several times (the AlphaZero loop). In this
  sandbox that's infeasible — search self-play is minutes per game on CPU — which
  is precisely why the competition allows real training spend and rewards trained
  models over rule-based search.
- **Train a policy too** (which line to search first), not just a value, to cut
  search width and sharpen move ordering.
- **Richer features / a small non-linear head** once there is enough on-policy data
  to train it without overfitting (the MLP overfit badly at this data size).

## Status summary
- Full pipeline runs end to end; the learned value is deployable (pure numpy).
- One-pass value net: strong predictor (AUC 0.78), weaker search heuristic (loses
  to the hand eval as replacement and as blend).
- Honest negative result + the AlphaZero-style path to actually beat the heuristic.
