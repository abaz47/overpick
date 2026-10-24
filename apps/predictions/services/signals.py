"""Pick flags — Over 2.5 and BTTS (independent)."""

from __future__ import annotations

from django.conf import settings

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
    """Independent tips: O2.5 and/or BTTS above thresholds.

    A match may carry both picks; UI shows one row with two columns.
    """
    thrs = thresholds_for_league(league_api_id)
    thr25 = thrs["o25"]
    thr_btts = float(
        thrs.get(
            "btts",
            getattr(settings, "SIGNAL_THRESHOLD_BTTS", 0.62),
        ),
    )
    pick_o25 = p25 >= thr25
    btts_p = 0.0 if p_btts is None else float(p_btts)
    pick_btts = p_btts is not None and btts_p >= thr_btts

    primary = None
    primary_edge = None
    if pick_o25:
        primary = "o25"
        primary_edge = p25 - thr25
    elif pick_btts:
        primary = "btts"
        primary_edge = btts_p - thr_btts

    return {
        "o15": False,
        "o25": pick_o25,
        "o35": False,
        "btts": pick_btts,
        "primary": primary,
        "primary_edge": primary_edge,
        "thresholds": {
            **dict(thrs),
            "btts": thr_btts,
        },
        "p_over_15": p15,
        "p_over_25": p25,
        "p_over_35": p35,
        "p_btts": btts_p if p_btts is not None else None,
    }
