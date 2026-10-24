"""Primary Pick flags — Over 2.5 only."""

from __future__ import annotations

from apps.predictions.services.league_thresholds import (
    thresholds_for_league,
)


def build_signal_flags(
    p15: float,
    p25: float,
    p35: float,
    *,
    league_api_id: int | None = None,
) -> dict:
    """Tip Over 2.5 when P clears the (league) threshold.

    O1.5 / O3.5 probabilities are stored for context but never
    become the primary Pick — the product is O2.5-focused.
    """
    thrs = thresholds_for_league(league_api_id)
    thr25 = thrs["o25"]
    pick = p25 >= thr25
    return {
        "o15": False,
        "o25": pick,
        "o35": False,
        "primary": "o25" if pick else None,
        "primary_edge": (p25 - thr25) if pick else None,
        "thresholds": dict(thrs),
        "p_over_15": p15,
        "p_over_25": p25,
        "p_over_35": p35,
    }
