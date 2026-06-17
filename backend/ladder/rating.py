"""Gaussian skill ratings (TrueSkill-style), implemented from scratch.

Each Submission's skill is modelled as a Gaussian N(mu, sigma^2): ``mu`` is the
estimated skill and ``sigma`` the uncertainty, which shrinks as we observe more
games. After a 1-v-1 episode we update both players with the standard TrueSkill
two-player equations, which give exactly the behaviour the competition asks for:

* the winner's mu goes up and the loser's mu goes down; a draw pulls the two
  mu values toward their mean;
* the size of the update scales with how *surprising* the result was given the
  prior mu values (the V/W functions), and with each player's own uncertainty
  (the sigma^2 / c factor) — an uncertain player moves more;
* sigma is reduced in proportion to the information the result provides (the W
  term); and
* only the win/draw/loss outcome matters — the score/margin never enters.

Defaults are the canonical TrueSkill values scaled so the initial mean is 600:
mu0 = 600, sigma0 = mu0/3 = 200, beta = sigma0/2 = 100.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

MU0 = 600.0
SIGMA0 = 200.0
BETA = 100.0          # performance noise: skill -> game-day performance
TAU = 2.0             # dynamics: skill can drift, so add a little variance back
DRAW_MARGIN = 18.0    # performance gap inside which a game is "a draw"
SIGMA_MIN = 25.0      # floor so uncertainty never fully collapses

_SQRT2 = math.sqrt(2.0)
_SQRT2PI = math.sqrt(2.0 * math.pi)


def _pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / _SQRT2PI


def _cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / _SQRT2))


# --- V / W for a decisive result (player 1 is the winner) ------------------- #
def _v_win(t: float, eps: float) -> float:
    denom = _cdf(t - eps)
    if denom < 1e-9:
        return -(t - eps)  # numerical guard for extreme upsets
    return _pdf(t - eps) / denom


def _w_win(t: float, eps: float) -> float:
    v = _v_win(t, eps)
    return v * (v + (t - eps))


# --- V / W for a draw (signed difference t = (mu1 - mu2)/c) ----------------- #
def _v_draw(t: float, eps: float) -> float:
    denom = _cdf(eps - t) - _cdf(-eps - t)
    if denom < 1e-9:
        return (-eps - t) if t < 0 else (eps - t)
    return (_pdf(-eps - t) - _pdf(eps - t)) / denom


def _w_draw(t: float, eps: float) -> float:
    denom = _cdf(eps - t) - _cdf(-eps - t)
    if denom < 1e-9:
        return 1.0
    v = _v_draw(t, eps)
    return v * v + (
        ((eps - t) * _pdf(eps - t) - (-eps - t) * _pdf(-eps - t)) / denom
    )


@dataclass
class Rating:
    mu: float = MU0
    sigma: float = SIGMA0

    @property
    def conservative(self) -> float:
        """Leaderboard-safe skill estimate (TrueSkill convention): mu - 3*sigma."""
        return self.mu - 3.0 * self.sigma


def expected_score(a: Rating, b: Rating) -> float:
    """P(a beats b) under the model — used only for reporting / matchmaking."""
    c = math.sqrt(2.0 * BETA * BETA + a.sigma ** 2 + b.sigma ** 2)
    return _cdf((a.mu - b.mu) / c)


def update_1v1(a: Rating, b: Rating, score_a: float) -> tuple[Rating, Rating]:
    """Return updated (a, b) ratings after a 1-v-1 episode.

    ``score_a`` is 1.0 (a won), 0.0 (b won) or 0.5 (draw). Margin is ignored.
    """
    # Skill can drift between games, so let uncertainty grow slightly first.
    sa2 = a.sigma ** 2 + TAU * TAU
    sb2 = b.sigma ** 2 + TAU * TAU
    c2 = sa2 + sb2 + 2.0 * BETA * BETA
    c = math.sqrt(c2)
    eps = DRAW_MARGIN / c

    if score_a == 0.5:
        t = (a.mu - b.mu) / c
        v = _v_draw(t, eps)
        w = _w_draw(t, eps)
        mu_a = a.mu + (sa2 / c) * v
        mu_b = b.mu - (sb2 / c) * v
    else:
        # Orient so player "w" is the winner.
        if score_a >= 1.0:
            (muw, sw2), (mul, sl2) = (a.mu, sa2), (b.mu, sb2)
        else:
            (muw, sw2), (mul, sl2) = (b.mu, sb2), (a.mu, sa2)
        t = (muw - mul) / c
        v = _v_win(t, eps)
        w = _w_win(t, eps)
        muw_new = muw + (sw2 / c) * v
        mul_new = mul - (sl2 / c) * v
        if score_a >= 1.0:
            mu_a, mu_b = muw_new, mul_new
        else:
            mu_b, mu_a = muw_new, mul_new

    sigma_a = math.sqrt(max(SIGMA_MIN ** 2, sa2 * (1.0 - (sa2 / c2) * w)))
    sigma_b = math.sqrt(max(SIGMA_MIN ** 2, sb2 * (1.0 - (sb2 / c2) * w)))
    return Rating(mu_a, sigma_a), Rating(mu_b, sigma_b)
