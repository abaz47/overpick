"""Independent Poisson helpers for match totals."""

from __future__ import annotations

import math


def poisson_pmf(k: int, lam: float) -> float:
    """P(K = k) for K ~ Poisson(lam)."""
    if lam < 0:
        raise ValueError("lambda must be >= 0")
    if k < 0:
        return 0.0
    if lam == 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lam) * (lam**k) / math.factorial(k)


def total_pmf(
    lambda_home: float,
    lambda_away: float,
    max_goals: int = 12,
) -> list[float]:
    """Distribution of total goals T = G_H + G_A."""
    probs = [0.0] * (max_goals + 1)
    for i in range(max_goals + 1):
        p_h = poisson_pmf(i, lambda_home)
        for j in range(max_goals + 1 - i):
            probs[i + j] += p_h * poisson_pmf(j, lambda_away)
    # Normalize tiny float drift into the last bin.
    tail = 1.0 - sum(probs)
    if tail > 0:
        probs[-1] += tail
    return probs


def p_over(
    lambda_home: float,
    lambda_away: float,
    threshold: float,
    max_goals: int = 12,
) -> float:
    """P(T > threshold) for Asian-style lines.

    O1.5 → threshold 1.5 → P(T >= 2)
    O2.5 → threshold 2.5 → P(T >= 3)
    O3.5 → threshold 3.5 → P(T >= 4)
    """
    min_goals = int(threshold) + 1
    probs = total_pmf(lambda_home, lambda_away, max_goals)
    return sum(probs[min_goals:])
