# Multi-turn lookahead — experimental scaffolding

The shipped agent searches a single turn: it plays each candidate line to the end
of **our** turn and scores the board there. It never sees the opponent's response
or our next turn — which is exactly why setup-heavy decks (evolution / Mega) get
little benefit, since their investment only pays off on later turns. This folder
extends the horizon so lines are judged **after the opponent responds**.

**It is experimental and NOT in the shipped bundle.** It runs, produces legal
games, and is fast — but across every opponent model tested it does **not
reliably beat** the single-turn agent (see *Measured findings* below). It is a
working framework and an honest negative result, with clear knobs to keep
exploring. The shipped `main.py` is unchanged.

## What it does
`agent_multiturn.py` is the shipped agent plus a horizon knob. At each of OUR
turn-ends inside the search, instead of evaluating immediately it:
1. **simulates the opponent's turn** (`_opponent_turn`) by driving the engine's
   own forward simulator with our heuristic — which plays for whoever is to move,
   since it keys off `state.yourIndex`;
2. then evaluates (horizon 1) or **plays our next turn** and evaluates (horizon 2).

```
_MULTITURN_HORIZON = 0   # single-turn — identical to the shipped agent
                   = 1   # our turn + opponent response          (2-ply)  [default]
                   = 2   # ... + our next turn                    (3-ply)

_OPP_MODEL = "threat"    # opponent only attaches one energy and attacks with its
                         # best real in-play attacker (uses no hidden-hand info)
           = "heuristic" # drive their full turn with our heuristic (plays their
                         # fake seeded hand too — noisier)

_SELECTIVE = True        # only look ahead when our active is in KO range;
                         # single-turn eval on safe turns (preserves breadth)
```
The defaults above are the **best-performing** multi-turn configuration found —
though "best" here still only matched single-turn (see findings).

## The hidden-information caveat (read this)
During our own turn the opponent never acts, so the single-turn search only needs
OUR hidden cards seeded accurately. To simulate the opponent's turn we must act
*for* them — but their hand and deck are hidden. The seeder fills those zones
with **legal filler**, not their real cards. Consequences:
- Their **visible board** (active/bench/attached energy) is accurate, so their
  attacks with already-in-play Pokemon are realistic.
- Their **draw for the turn and hand plays are fake**, so anything depending on
  their real hand is only approximate.

So a multi-turn value is a *better-but-noisier* estimate than the single-turn one.
Sharpening the opponent model is the main lever for making it pay off.

## How to run
From a copy of the Simulation bundle that also contains a `gauntlet/` folder
(copy it from `ptcg-gauntlet/decks`) and `agent_multiturn.py`:

    cp -r /path/to/ptcg-gauntlet/decks ./gauntlet
    cp /path/to/ptcg-multiturn/*.py .
    python3 multiturn_eval.py [horizon] [games_per_deck] [deck_substring]

The harness loads the agent twice — once at the horizon under test, once at
horizon 0 — so the A/B isolates the *effect of the horizon* and nothing else:

    python3 multiturn_eval.py 1 6 mega     # horizon-1 vs single-turn on Mega decks
    python3 multiturn_eval.py 2 6          # horizon-2 vs single-turn on setup decks
    python3 multiturn_eval.py 1 6 aggro    # sanity: should stay ~50% on aggro

## Measured findings (opponent-model experiment)
All A/B vs the single-turn agent (horizon 0), same deck both sides, self-play.
Absolute rates are directional (small samples), so read them as "beats / ties /
loses single-turn," not as ladder estimates.

| Configuration | Slice | Result vs single-turn |
|---|---|---|
| Heuristic opponent, every turn | setup decks | ~45% (loses) |
| **Threat** opponent, every turn | setup decks | 38.9% (loses) |
| Threat vs Heuristic (head-to-head) | setup decks | 52.8% (threat marginally better model) |
| **Selective** + threat | setup decks (6, 48 g) | 66.7% — *looked like a win* |
| **Selective** + threat | setup decks (10, 80 g) | **50.0% (neutral)** — did **not** replicate |
| Selective + threat | aggro decks | 53.3% (neutral, as intended) |

**Verdict: multi-turn lookahead does not reliably beat single-turn here.** The
sharper (threat) opponent model is a slightly better *model* than the heuristic
but still doesn't help. Selectively looking ahead only when threatened is the
right instinct and looked promising on a small sample, but the effect vanished on
a larger, broader one (only 3/10 decks favored) — the initial 66.7% was
small-sample noise. This is an honest negative result, and a useful one: the
single-turn search is a strong baseline even on setup decks, and the obvious
2-ply extensions don't clear it.

**Why it's hard (best current read):** the opponent model is approximate under
hidden information; `_eval` is tuned for our-turn-end boards, not post-opponent
ones; and looking ahead to a worst-case response makes many lines look similarly
bad, drowning out the discrimination between *our* choices while costing search
breadth. These are the reasons the competition rewards trained value/opponent
models over rule-based lookahead.

## Levers still worth trying (for future work)
1. **Horizon-aware evaluation** — score post-opponent boards on their own terms
   (survived attacker, prize swing, our next-turn KO reachability) rather than
   reusing the our-turn-end `_eval`. Most likely to move the needle.
2. **A learned or archetype-seeded opponent hand**, instead of filler, so their
   plays reflect real threats (addresses the hidden-info root cause).
3. **More compute for depth without losing breadth** — raise `_STEP_BUDGET` /
   `_TIME_BUDGET` (keep the latter well under the Kaggle per-turn limit) so the
   opponent sim doesn't crowd out first-action search.
4. **A tighter selective trigger** — e.g. only on setup turns *and* when a
   specific evolve/attach decision is on the table, not merely "in KO range."

## Status summary
- Runs, legal, fast (~1 s/game); anti-stall guard inherited; not in the bundle.
- Best config (selective + threat, horizon 1) = **neutral** vs single-turn; the
  earlier positive did not replicate.
- Delivered as a working framework + honest negative result; the levers above are
  the path if you want to keep pushing the evolution/Mega ceiling.
