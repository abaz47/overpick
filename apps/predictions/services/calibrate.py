"""Choose global and per-league Pick thresholds."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from apps.predictions.services.backtest import (
    DEFAULT_THRESHOLDS,
    BacktestReport,
    BacktestRow,
    run_backtest,
)
from apps.predictions.services.league_thresholds import (
    MARKETS,
    save_league_thresholds,
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


def _best_for_rows(
    rows: list[BacktestRow],
    market: str,
    *,
    min_coverage: float,
) -> CalibratedThreshold | None:
    n = len(rows)
    if n == 0:
        return None
    report = BacktestReport(rows=rows)
    best: CalibratedThreshold | None = None
    for tr in report.threshold_grid(
        market,
        DEFAULT_THRESHOLDS[market],
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


def calibrate_all(
    *,
    current: dict[str, float],
    min_coverage: float = MIN_COVERAGE,
    min_delta: float = MIN_DELTA,
) -> dict[str, CalibratedThreshold | None]:
    """Return suggested global thr per market."""
    report = run_backtest()
    out: dict[str, CalibratedThreshold | None] = {}
    for market in MARKETS:
        best = _best_for_rows(
            report.rows,
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
) -> dict[str, dict[str, float]]:
    """Per-league overrides where sample is large enough."""
    report = run_backtest()
    by_league: dict[int, list[BacktestRow]] = defaultdict(
        list,
    )
    for row in report.rows:
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
) -> tuple[dict[str, dict[str, float]], object]:
    """Calibrate and persist league_thresholds.json."""
    if global_thr is None:
        from django.conf import settings

        global_thr = {
            "o15": float(settings.SIGNAL_THRESHOLD_O15),
            "o25": float(settings.SIGNAL_THRESHOLD_O25),
            "o35": float(settings.SIGNAL_THRESHOLD_O35),
        }
    data = calibrate_leagues(global_thr=global_thr)
    path = save_league_thresholds(data)
    return data, path
