"""Poisson / Dixon–Coles helpers for match totals."""

from __future__ import annotations

import math

from django.conf import settings


def poisson_pmf(k: int, lam: float) -> float:
    """P(K = k) for K ~ Poisson(lam)."""
    if lam < 0:
        raise ValueError("lambda must be >= 0")
    if k < 0:
        return 0.0
    if lam == 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lam) * (lam**k) / math.factorial(k)


def dixon_coles_tau(
    home_goals: int,
    away_goals: int,
    lambda_home: float,
    lambda_away: float,
    rho: float,
) -> float:
    """Dixon–Coles low-score dependence factor τ."""
    if home_goals == 0 and away_goals == 0:
        return 1.0 - lambda_home * lambda_away * rho
    if home_goals == 0 and away_goals == 1:
        return 1.0 + lambda_home * rho
    if home_goals == 1 and away_goals == 0:
        return 1.0 + lambda_away * rho
    if home_goals == 1 and away_goals == 1:
        return 1.0 - rho
    return 1.0


def score_matrix(
    lambda_home: float,
    lambda_away: float,
    *,
    max_goals: int = 12,
    rho: float | None = None,
) -> list[list[float]]:
    """Joint P(home=i, away=j), optionally Dixon–Coles adjusted."""
    if rho is None:
        rho = float(getattr(settings, "MODEL_DC_RHO", -0.1))
    matrix = [[0.0] * (max_goals + 1) for _ in range(max_goals + 1)]
    total = 0.0
    for i in range(max_goals + 1):
        p_h = poisson_pmf(i, lambda_home)
        for j in range(max_goals + 1):
            p = (
                p_h
                * poisson_pmf(j, lambda_away)
                * dixon_coles_tau(
                    i,
                    j,
                    lambda_home,
                    lambda_away,
                    rho,
                )
            )
            # Keep probabilities non-negative.
            p = max(p, 0.0)
            matrix[i][j] = p
            total += p
    if total > 0:
        for i in range(max_goals + 1):
            for j in range(max_goals + 1):
                matrix[i][j] /= total
    return matrix


def total_pmf(
    lambda_home: float,
    lambda_away: float,
    max_goals: int = 12,
    *,
    rho: float | None = None,
) -> list[float]:
    """Distribution of total goals T = G_H + G_A."""
    matrix = score_matrix(
        lambda_home,
        lambda_away,
        max_goals=max_goals,
        rho=rho,
    )
    probs = [0.0] * (max_goals + 1)
    for i in range(max_goals + 1):
        for j in range(max_goals + 1 - i):
            probs[i + j] += matrix[i][j]
    # Fold unreachable high totals into the last bin.
    tail = 1.0 - sum(probs)
    if abs(tail) > 1e-12:
        probs[-1] += tail
    return probs


def p_over(
    lambda_home: float,
    lambda_away: float,
    threshold: float,
    max_goals: int = 12,
    *,
    rho: float | None = None,
) -> float:
    """P(T > threshold) for Asian-style lines.

    O1.5 → threshold 1.5 → P(T >= 2)
    O2.5 → threshold 2.5 → P(T >= 3)
    O3.5 → threshold 3.5 → P(T >= 4)
    """
    min_goals = int(threshold) + 1
    probs = total_pmf(
        lambda_home,
        lambda_away,
        max_goals,
        rho=rho,
    )
    return sum(probs[min_goals:])


def p_btts(
    lambda_home: float,
    lambda_away: float,
    max_goals: int = 12,
    *,
    rho: float | None = None,
) -> float:
    """P(both teams score) = P(G_H>=1 and G_A>=1)."""
    matrix = score_matrix(
        lambda_home,
        lambda_away,
        max_goals=max_goals,
        rho=rho,
    )
    # 1 - P(home 0) - P(away 0) + P(0-0)
    p_home0 = sum(matrix[0][j] for j in range(max_goals + 1))
    p_away0 = sum(matrix[i][0] for i in range(max_goals + 1))
    p_00 = matrix[0][0]
    return max(0.0, min(1.0, 1.0 - p_home0 - p_away0 + p_00))
