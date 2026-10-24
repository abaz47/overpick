"""Tests for Poisson totals helpers."""

from apps.predictions.services.poisson import (
    p_over,
    poisson_pmf,
    total_pmf,
)


def test_poisson_pmf_sums_near_one() -> None:
    total = sum(poisson_pmf(k, 2.5) for k in range(0, 20))
    assert 0.999 < total <= 1.0


def test_p_over_increases_with_lambda() -> None:
    low = p_over(1.0, 0.8, 2.5)
    high = p_over(2.0, 1.8, 2.5)
    assert high > low


def test_p_over_15_for_high_lambda() -> None:
    # λ≈3.5 → P(T>=2) should be high.
    prob = p_over(2.0, 1.5, 1.5)
    assert prob > 0.8


def test_total_pmf_length() -> None:
    probs = total_pmf(1.2, 1.1, max_goals=8)
    assert len(probs) == 9
    assert abs(sum(probs) - 1.0) < 1e-9
