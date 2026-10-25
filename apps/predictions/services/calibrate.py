"""Choose global and per-league Pick thresholds."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from apps.predictions.services.backtest import (
    DEFAULT_THRESHOLDS,
    BacktestRow,
    ThresholdResult,
    run_backtest,
)
from apps.predictions.services.league_thresholds import (
    MARKETS,
    save_league_thresholds,
)
from apps.predictions.services.prob_calibration import (
    calibrate_o25,
    fit_o25_calibration,
    save_o25_calibration,
)

MIN_COVERAGE = 0.05
MIN_DELTA = 0.02
# Min finished rows in a league before custom thr.
MIN_LEAGUE_ROWS = 400


@dataclass
class CalibratedThreshold:
    """Suggested threshold for one market."""

    market: str
    threshold: float
    hit_rate: float
    signals: int
    coverage: float
    score: float


def _prob_hit(
    row: BacktestRow,
    market: str,
) -> tuple[float, bool]:
    """Probability used for tipping (calibrated for O2.5)."""
    if market == "o25":
        return calibrate_o25(row.p_over_25), row.hit_25
    if market == "o15":
        return row.p_over_15, row.hit_15
    if market == "o35":
        return row.p_over_35, row.hit_35
    if market == "btts":
        return row.p_btts, row.hit_btts
    raise KeyError(market)


def _threshold_grid_rows(
    rows: list[BacktestRow],
    market: str,
    thresholds: list[float],
) -> list[ThresholdResult]:
    results = []
    for thr in thresholds:
        signals = 0
        hits = 0
        for row in rows:
            p, hit = _prob_hit(row, market)
            if p >= thr:
                signals += 1
                if hit:
                    hits += 1
        results.append(
            ThresholdResult(
                market=market,
                threshold=thr,
                signals=signals,
                hits=hits,
            ),
        )
    return results


def _best_for_rows(
    rows: list[BacktestRow],
    market: str,
    *,
    min_coverage: float,
) -> CalibratedThreshold | None:
    n = len(rows)
    if n == 0:
        return None
    best: CalibratedThreshold | None = None
    for tr in _threshold_grid_rows(
        rows,
        market,
        list(DEFAULT_THRESHOLDS[market]),
    ):
        if tr.hit_rate is None or tr.signals == 0:
            continue
        cov = tr.signals / n
        if cov < min_coverage:
            continue
        score = abs(tr.hit_rate - tr.threshold)
        cand = CalibratedThreshold(
            market=market,
            threshold=tr.threshold,
            hit_rate=tr.hit_rate,
            signals=tr.signals,
            coverage=cov,
            score=score,
        )
        if (
            best is None
            or cand.score < best.score
            or (
                abs(cand.score - best.score) < 1e-12
                and cand.coverage > best.coverage
            )
        ):
            best = cand
    return best


def fit_probability_calibration(
    rows: list[BacktestRow] | None = None,
) -> object:
    """Fit and persist O2.5 raw→calibrated map from backtest."""
    if rows is None:
        rows = run_backtest().rows
    pairs = [(r.p_over_25, r.hit_25) for r in rows]
    knots = fit_o25_calibration(pairs)
    return save_o25_calibration(knots)


def calibrate_all(
    *,
    current: dict[str, float],
    min_coverage: float = MIN_COVERAGE,
    min_delta: float = MIN_DELTA,
    rows: list[BacktestRow] | None = None,
) -> dict[str, CalibratedThreshold | None]:
    """Return suggested global thr per market (O2.5 on P_cal)."""
    if rows is None:
        rows = run_backtest().rows
    out: dict[str, CalibratedThreshold | None] = {}
    for market in MARKETS:
        best = _best_for_rows(
            rows,
            market,
            min_coverage=min_coverage,
        )
        if best is None:
            out[market] = None
            continue
        if abs(best.threshold - current[market]) < min_delta:
            out[market] = None
            continue
        out[market] = best
    return out


def calibrate_leagues(
    *,
    global_thr: dict[str, float],
    min_rows: int = MIN_LEAGUE_ROWS,
    min_coverage: float = 0.04,
    rows: list[BacktestRow] | None = None,
) -> dict[str, dict[str, float]]:
    """Per-league overrides where sample is large enough."""
    if rows is None:
        rows = run_backtest().rows
    by_league: dict[int, list[BacktestRow]] = defaultdict(
        list,
    )
    for row in rows:
        by_league[row.league_api_id].append(row)

    result: dict[str, dict[str, float]] = {}
    for league_id, rows in sorted(by_league.items()):
        if len(rows) < min_rows:
            continue
        league_thr: dict[str, float] = {}
        for market in MARKETS:
            best = _best_for_rows(
                rows,
                market,
                min_coverage=min_coverage,
            )
            if best is None:
                continue
            base = global_thr[market]
            # Only stricter (higher) overrides — never weaken.
            if best.threshold < base + MIN_DELTA:
                continue
            league_thr[market] = best.threshold
        if league_thr:
            result[str(league_id)] = league_thr
    return result


def write_league_calibration(
    global_thr: dict[str, float] | None = None,
    rows: list[BacktestRow] | None = None,
) -> tuple[dict[str, dict[str, float]], object]:
    """Calibrate and persist league_thresholds.json."""
    if global_thr is None:
        from django.conf import settings

        global_thr = {
            "o15": float(settings.SIGNAL_THRESHOLD_O15),
            "o25": float(settings.SIGNAL_THRESHOLD_O25),
            "o35": float(settings.SIGNAL_THRESHOLD_O35),
        }
    data = calibrate_leagues(
        global_thr=global_thr,
        rows=rows,
    )
    path = save_league_thresholds(data)
    return data, path
