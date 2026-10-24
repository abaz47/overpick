"""Pick flags — Over 2.5 only."""

from __future__ import annotations

from apps.predictions.services.league_thresholds import (
    thresholds_for_league,
)


def build_signal_flags(
    p15: float,
    p25: float,
    p35: float,
    *,
    p_btts: float | None = None,
    league_api_id: int | None = None,
) -> dict:
    """Product tip: Over 2.5 above league/global threshold.

    ``p_btts`` is accepted for API compatibility but never tipped.
    """
    _ = p_btts
    thrs = thresholds_for_league(league_api_id)
    thr25 = thrs["o25"]
    pick_o25 = p25 >= thr25

    return {
        "o15": False,
        "o25": pick_o25,
        "o35": False,
        "btts": False,
        "primary": "o25" if pick_o25 else None,
        "primary_edge": (p25 - thr25) if pick_o25 else None,
        "thresholds": dict(thrs),
        "p_over_15": p15,
        "p_over_25": p25,
        "p_over_35": p35,
    }
