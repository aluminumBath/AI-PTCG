"""Validate tournament results — are the numbers in a sane range, and how much
is just small-sample noise?

Two pieces:

* ``validate_tournament(result)`` attaches a 95% Wilson confidence interval and
  standard error to every win rate, then runs sanity checks (enough games?
  is the random baseline near the bottom? draw rate reasonable? any matchups too
  small to trust? are adjacent ranks actually separated or within noise?).

* ``run_consistency(...)`` replays one matchup over several independent seeded
  batches and reports each batch's win rate plus the **mean and standard
  deviation** across batches — a direct read on how consistent a model is.
"""
from __future__ import annotations

import math
import random
import statistics
from typing import Callable, Optional

from engine.game import GameEngine
from eval.tournament import play_match


# --------------------------------------------------------------------------- #
# Proportion statistics
# --------------------------------------------------------------------------- #
def wilson_interval(wins: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval for a binomial proportion (default z=1.96)."""
    if n <= 0:
        return (0.0, 0.0)
    p = wins / n
    denom = 1.0 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def proportion_se(wins: int, n: int) -> float:
    if n <= 0:
        return 0.0
    p = wins / n
    return math.sqrt(p * (1 - p) / n)


def summarize_rate(wins: int, n: int) -> dict:
    lo, hi = wilson_interval(wins, n)
    return {
        "p": round(wins / n, 3) if n else 0.0,
        "se": round(proportion_se(wins, n), 3),
        "ci_lo": round(lo, 3),
        "ci_hi": round(hi, 3),
        "ci_half": round((hi - lo) / 2, 3),
        "n": n,
    }


# --------------------------------------------------------------------------- #
# Tournament validation
# --------------------------------------------------------------------------- #
def validate_tournament(result: dict) -> dict:
    standings = result.get("standings", [])
    matrix = result.get("matrix", {})
    agents = result.get("agents", [])

    # Per-agent win-rate summaries (overall and decided).
    winrates: dict[str, dict] = {}
    for s in standings:
        decided = s["wins"] + s["losses"]
        winrates[s["agent"]] = {
            "overall": summarize_rate(s["wins"], s["games"]),
            "decided": summarize_rate(s["wins"], decided),
            "wins": s["wins"], "losses": s["losses"], "draws": s["draws"],
            "games": s["games"],
        }

    checks: list[dict] = []

    # 1) Sample adequacy — how wide is the widest CI?
    halves = [w["overall"]["ci_half"] for w in winrates.values() if w["games"]]
    worst = max(halves) if halves else 0.0
    if worst <= 0.06:
        checks.append({"id": "sample", "status": "pass",
                       "label": "Sample size",
                       "detail": f"Win rates are tight (widest 95% CI is ±{worst:.0%}). Results are well-resolved."})
    elif worst <= 0.12:
        checks.append({"id": "sample", "status": "info",
                       "label": "Sample size",
                       "detail": f"Moderate sample: widest 95% CI is ±{worst:.0%}. Increase games per pairing to tighten."})
    else:
        checks.append({"id": "sample", "status": "warn",
                       "label": "Sample size",
                       "detail": f"Small sample: widest 95% CI is ±{worst:.0%}. Treat the ranking as provisional and run more games."})

    # 2) Draw rate — too many ties usually means games hitting the turn cap.
    total_games = sum(s["games"] for s in standings)
    total_draws = sum(s["draws"] for s in standings)  # each draw counted on both sides
    draw_rate = (total_draws / total_games) if total_games else 0.0  # ~fraction of games drawn
    if draw_rate <= 0.10:
        checks.append({"id": "draws", "status": "pass", "label": "Draw rate",
                       "detail": f"Draw rate {draw_rate:.0%} — games are resolving normally."})
    elif draw_rate <= 0.25:
        checks.append({"id": "draws", "status": "info", "label": "Draw rate",
                       "detail": f"Draw rate {draw_rate:.0%} — a few games stall to the turn cap."})
    else:
        checks.append({"id": "draws", "status": "warn", "label": "Draw rate",
                       "detail": f"High draw rate {draw_rate:.0%} — many games hit the turn cap; win rates may be unreliable."})

    # 3) Baseline sanity — the random agent should sit near the bottom, and a
    #    strong agent should beat it with a CI-separated margin.
    if "random" in winrates and len(standings) >= 2:
        order = [s["agent"] for s in standings]            # already sorted best->worst
        rank = order.index("random")
        bottom_third = rank >= max(1, int(len(order) * 2 / 3))
        rnd = winrates["random"]["overall"]
        top = standings[0]["agent"]
        top_ci = winrates[top]["overall"]
        separated = top_ci["ci_lo"] > rnd["ci_hi"]
        if bottom_third and separated:
            checks.append({"id": "baseline", "status": "pass", "label": "Baseline sanity",
                           "detail": f"Random ranks {rank + 1}/{len(order)} and the top model's CI is clear of it — ordering looks correct."})
        elif separated:
            checks.append({"id": "baseline", "status": "info", "label": "Baseline sanity",
                           "detail": f"Top model beats random with separation, but random ranks {rank + 1}/{len(order)} (higher than expected)."})
        else:
            checks.append({"id": "baseline", "status": "warn", "label": "Baseline sanity",
                           "detail": "The random baseline is not clearly beaten (overlapping CIs) — check the agents or run more games."})
    else:
        checks.append({"id": "baseline", "status": "info", "label": "Baseline sanity",
                       "detail": "Add the 'random' model to the field to anchor the ranking against a known-weak baseline."})

    # 4) Rank separation — are the top two actually distinguishable?
    if len(standings) >= 2:
        a, b = standings[0]["agent"], standings[1]["agent"]
        ca, cb = winrates[a]["overall"], winrates[b]["overall"]
        overlap = not (ca["ci_lo"] > cb["ci_hi"] or cb["ci_lo"] > ca["ci_hi"])
        if overlap:
            checks.append({"id": "separation", "status": "info", "label": "Top-rank separation",
                           "detail": f"#1 {a} and #2 {b} have overlapping 95% CIs — their order is within noise; more games would separate them."})
        else:
            checks.append({"id": "separation", "status": "pass", "label": "Top-rank separation",
                           "detail": f"#1 {a} is statistically ahead of #2 {b} (non-overlapping CIs)."})

    # 5) Unreliable matchups — decided pairs that are too small or all-or-nothing.
    shaky = []
    for i, a in enumerate(agents):
        for bb in agents[i + 1:]:
            wa = matrix.get(a, {}).get(bb, 0)
            wb = matrix.get(bb, {}).get(a, 0)
            n = wa + wb
            if n == 0:
                continue
            if n < 4 or wa == 0 or wa == n:
                shaky.append(f"{a} vs {bb} ({wa}/{n})")
    if not shaky:
        checks.append({"id": "matchups", "status": "pass", "label": "Per-matchup reliability",
                       "detail": "No head-to-head pair is decided on too few games."})
    else:
        preview = "; ".join(shaky[:5]) + (" …" if len(shaky) > 5 else "")
        checks.append({"id": "matchups", "status": "warn", "label": "Per-matchup reliability",
                       "detail": f"{len(shaky)} matchup(s) decided on very few games (extreme rates unreliable): {preview}"})

    n_warn = sum(1 for c in checks if c["status"] == "warn")
    verdict = "warn" if n_warn else ("info" if any(c["status"] == "info" for c in checks) else "pass")
    return {
        "winrates": winrates,
        "checks": checks,
        "verdict": verdict,
        "games_played": result.get("games_played"),
        "games_per_pairing": result.get("games_per_pairing"),
    }


# --------------------------------------------------------------------------- #
# Consistency: repeated independent batches -> mean ± standard deviation
# --------------------------------------------------------------------------- #
def run_consistency(
    agent_a: str,
    agent_b: str,
    deck_ids: list[str],
    batches: int,
    games_per_batch: int,
    deck_resolver: Callable[[str], list],
    checkpoint: Optional[str] = None,
    seed: int = 0,
    progress: Optional[Callable[[int, int], None]] = None,
    should_continue: Optional[Callable[[], bool]] = None,
) -> dict:
    """Replay agent_a vs agent_b over ``batches`` independent batches of
    ``games_per_batch`` games (sides + decks alternate within each batch).
    Returns each batch's win rate for agent_a plus the mean and standard
    deviation across batches, and a pooled 95% CI."""
    from agents.registry import make_agent
    a = make_agent(agent_a, checkpoint)
    b = make_agent(agent_b, checkpoint)
    rng = random.Random(seed)
    decks = deck_ids or ["charizard_ex"]

    per_batch = []
    done = 0
    total = max(1, batches * games_per_batch)
    cancelled = False
    for k in range(batches):
        wins = decided = 0
        for g in range(games_per_batch):
            if should_continue and not should_continue():
                cancelled = True
                break
            a_seat = 0 if g % 2 == 0 else 1
            seat0, seat1 = (a, b) if a_seat == 0 else (b, a)
            d0 = decks[g % len(decks)]
            d1 = decks[(g + 1) % len(decks)]
            winner, _ = play_match(seat0, seat1, deck_resolver(d0), deck_resolver(d1),
                                   seed=rng.randint(0, 2**31 - 1))
            if winner is not None:
                decided += 1
                if winner == a_seat:
                    wins += 1
            done += 1
            if progress:
                progress(done, total)
        per_batch.append({
            "batch": k + 1, "wins": wins, "decided": decided,
            "winrate": round(wins / decided, 3) if decided else None,
        })
        if cancelled:
            break

    rates = [pb["winrate"] for pb in per_batch if pb["winrate"] is not None]
    mean = round(statistics.mean(rates), 3) if rates else 0.0
    std = round(statistics.pstdev(rates), 3) if len(rates) > 1 else 0.0
    tot_wins = sum(pb["wins"] for pb in per_batch)
    tot_decided = sum(pb["decided"] for pb in per_batch)
    lo, hi = wilson_interval(tot_wins, tot_decided)

    spread = (max(rates) - min(rates)) if rates else 0.0
    if std <= 0.07:
        note = f"Very consistent: batch win rates vary by only ±{std:.0%} (SD)."
    elif std <= 0.15:
        note = f"Moderately consistent: batch win rates have SD ±{std:.0%}."
    else:
        note = f"High variance: batch win rates swing with SD ±{std:.0%} — results depend heavily on the run."

    return {
        "agent_a": agent_a, "agent_b": agent_b,
        "batches": batches, "games_per_batch": games_per_batch,
        "per_batch": per_batch,
        "mean": mean, "std": std, "spread": round(spread, 3),
        "pooled_winrate": round(tot_wins / tot_decided, 3) if tot_decided else 0.0,
        "ci_lo": round(lo, 3), "ci_hi": round(hi, 3),
        "decided": tot_decided, "note": note, "cancelled": cancelled,
        "perspective": agent_a,
    }
