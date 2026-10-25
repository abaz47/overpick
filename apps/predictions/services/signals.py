"""Pick flags — Over 2.5 on hybrid P (cal Poisson + GBM)."""

from __future__ import annotations

from apps.predictions.services.gbm_features import (
    hybrid_probability,
)
from apps.predictions.services.gbm_model import predict_proba
from apps.predictions.services.league_thresholds import (
    thresholds_for_league,
)
from apps.predictions.services.prob_calibration import (
    calibrate_o25,
)


def build_signal_flags(
    p15: float,
    p25: float,
    p35: float,
    *,
    p_btts: float | None = None,
    league_api_id: int | None = None,
    gbm_features: dict[str, float] | None = None,
    p_gbm: float | None = None,
) -> dict:
    """Product tip: hybrid P(O2.5) above league/global thr.

    ``hybrid = 0.5 * P_cal + 0.5 * P_gbm``. If GBM is
    unavailable, falls back to calibrated Poisson only.
    ``p_btts`` is accepted for API compatibility but never tipped.
    """
    _ = p_btts
    thrs = thresholds_for_league(league_api_id)
    thr25 = thrs["o25"]
    p25_cal = calibrate_o25(p25)

    gbm_p = p_gbm
    if gbm_p is None and gbm_features is not None:
        gbm_p = predict_proba(gbm_features)

    if gbm_p is None:
        tip_p = p25_cal
        p_hybrid = p25_cal
    else:
        p_hybrid = hybrid_probability(p25_cal, gbm_p)
        tip_p = p_hybrid

    pick_o25 = tip_p >= thr25

    return {
        "o15": False,
        "o25": pick_o25,
        "o35": False,
        "btts": False,
        "primary": "o25" if pick_o25 else None,
        "primary_edge": (tip_p - thr25) if pick_o25 else None,
        "thresholds": dict(thrs),
        "p_over_15": p15,
        "p_over_25": p25,
        "p_over_25_cal": p25_cal,
        "p_gbm": gbm_p,
        "p_hybrid": p_hybrid,
        "p_over_35": p35,
        "tip_scale": "hybrid" if gbm_p is not None else "cal",
    }
