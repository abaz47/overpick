"""Walk-forward backtest for poisson_v1 threshold calibration."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field

from django.conf import settings

from apps.matches.models import Fixture
from apps.predictions.services.form import (
    FINISHED,
    blend,
    shrink,
)
from apps.predictions.services.poisson import p_over

Markets = ("o15", "o25", "o35")


@dataclass
class BacktestRow:
    """One scored forecast vs actual total."""

    fixture_id: int
    league_api_id: int
    season: int
    country: str
    league_name: str
    total_goals: int
    p_over_15: float
    p_over_25: float
    p_over_35: float
    lambda_total: float

    @property
    def hit_15(self) -> bool:
        return self.total_goals >= 2

    @property
    def hit_25(self) -> bool:
        return self.total_goals >= 3

    @property
    def hit_35(self) -> bool:
        return self.total_goals >= 4


@dataclass
class ThresholdResult:
    """Hit stats for one market threshold."""

    market: str
    threshold: float
    signals: int
    hits: int

    @property
    def hit_rate(self) -> float | None:
        if self.signals == 0:
            return None
        return self.hits / self.signals

    @property
    def coverage(self) -> float:
        return self.signals


@dataclass
class BacktestReport:
    """Aggregated calibration output."""

    rows: list[BacktestRow] = field(default_factory=list)
    skipped: int = 0
    considered: int = 0

    def base_rates(self) -> dict[str, float]:
        n = len(self.rows)
        if n == 0:
            return {"o15": 0.0, "o25": 0.0, "o35": 0.0}
        return {
            "o15": sum(r.hit_15 for r in self.rows) / n,
            "o25": sum(r.hit_25 for r in self.rows) / n,
            "o35": sum(r.hit_35 for r in self.rows) / n,
        }

    def reliability_bins(
        self,
        market: str,
        step: float = 0.1,
    ) -> list[dict]:
        """Predicted-prob bins vs empirical frequency."""
        attr = {
            "o15": ("p_over_15", "hit_15"),
            "o25": ("p_over_25", "hit_25"),
            "o35": ("p_over_35", "hit_35"),
        }[market]
        p_attr, hit_attr = attr
        buckets: dict[int, list[tuple[float, bool]]] = defaultdict(
            list,
        )
        for row in self.rows:
            p = getattr(row, p_attr)
            hit = getattr(row, hit_attr)
            idx = min(int(p / step), int(1.0 / step) - 1)
            if idx < 0:
                idx = 0
            buckets[idx].append((p, hit))
        out = []
        for idx in sorted(buckets):
            items = buckets[idx]
            lo = idx * step
            hi = lo + step
            avg_p = sum(p for p, _ in items) / len(items)
            freq = sum(h for _, h in items) / len(items)
            out.append(
                {
                    "bin": f"{lo:.1f}-{hi:.1f}",
                    "n": len(items),
                    "avg_p": avg_p,
                    "freq": freq,
                },
            )
        return out

    def threshold_grid(
        self,
        market: str,
        thresholds: Iterable[float],
    ) -> list[ThresholdResult]:
        p_attr, hit_attr = {
            "o15": ("p_over_15", "hit_15"),
            "o25": ("p_over_25", "hit_25"),
            "o35": ("p_over_35", "hit_35"),
        }[market]
        results = []
        for thr in thresholds:
            signals = 0
            hits = 0
            for row in self.rows:
                if getattr(row, p_attr) >= thr:
                    signals += 1
                    if getattr(row, hit_attr):
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

    def by_season(self, market: str = "o25") -> list[dict]:
        """Base rate and mean P by season."""
        p_attr, hit_attr = {
            "o15": ("p_over_15", "hit_15"),
            "o25": ("p_over_25", "hit_25"),
            "o35": ("p_over_35", "hit_35"),
        }[market]
        groups: dict[int, list[BacktestRow]] = defaultdict(list)
        for row in self.rows:
            groups[row.season].append(row)
        out = []
        for season in sorted(groups):
            items = groups[season]
            n = len(items)
            out.append(
                {
                    "season": season,
                    "n": n,
                    "base": sum(getattr(r, hit_attr) for r in items) / n,
                    "avg_p": sum(getattr(r, p_attr) for r in items) / n,
                },
            )
        return out


def _mean_pair(
    samples: list[tuple[float, float]],
    limit: int | None = None,
) -> tuple[float, float, int]:
    """Average scored/conceded from (scored, conceded) samples."""
    if not samples:
        return 0.0, 0.0, 0
    chunk = samples[-limit:] if limit else samples
    n = len(chunk)
    scored = sum(s for s, _ in chunk) / n
    conceded = sum(c for _, c in chunk) / n
    return scored, conceded, n


def _league_mu(
    samples: list[tuple[int, int]],
) -> tuple[float, float]:
    if not samples:
        return 1.3, 1.1
    n = len(samples)
    hs = sum(gh for gh, _ in samples) / n
    as_ = sum(ga for _, ga in samples) / n
    return hs, as_


def iter_backtest_rows(
    fixtures: Iterable[Fixture],
    *,
    n: int | None = None,
    min_n: int | None = None,
    shrink_k: float | None = None,
    last_weight: float | None = None,
) -> Iterator[tuple[BacktestRow | None, int, int]]:
    """Yield (row|None, season, league_api_id) in order.

    Maintains in-memory histories so each forecast uses
    only matches strictly before the current kickoff.
    row is None when form sample is below MODEL_MIN_N.
    """
    n = n if n is not None else settings.MODEL_N
    min_n = (
        min_n
        if min_n is not None
        else int(getattr(settings, "MODEL_MIN_N", 3))
    )
    shrink_k = (
        shrink_k
        if shrink_k is not None
        else float(getattr(settings, "MODEL_SHRINK_K", 3.0))
    )
    last_weight = (
        last_weight
        if last_weight is not None
        else float(
            getattr(settings, "MODEL_LAST_WEIGHT", 0.6),
        )
    )

    home_hist: dict[int, list[tuple[float, float]]] = defaultdict(list)
    away_hist: dict[int, list[tuple[float, float]]] = defaultdict(list)
    home_league: dict[
        tuple[int, int],
        list[tuple[float, float]],
    ] = defaultdict(list)
    away_league: dict[
        tuple[int, int],
        list[tuple[float, float]],
    ] = defaultdict(list)
    league_hist: dict[int, list[tuple[int, int]]] = defaultdict(list)

    for fixture in fixtures:
        home_id = fixture.home_id
        away_id = fixture.away_id
        league_id = fixture.league_id
        gh = int(fixture.goals_home)
        ga = int(fixture.goals_away)

        hs_l, hc_l, n_hl = _mean_pair(
            home_hist[home_id],
            limit=n,
        )
        as_l, ac_l, n_al = _mean_pair(
            away_hist[away_id],
            limit=n,
        )
        enough = n_hl >= min_n and n_al >= min_n

        league = fixture.league
        league_api = league.api_id
        row: BacktestRow | None = None
        if enough:
            mu_hs, mu_as = _league_mu(league_hist[league_id])
            mu_hc, mu_ac = mu_as, mu_hs
            hs_s, hc_s, n_hs = _mean_pair(
                home_league[(home_id, league_id)],
            )
            as_s, ac_s, n_as = _mean_pair(
                away_league[(away_id, league_id)],
            )
            hs_season = hs_s if n_hs else mu_hs
            hc_season = hc_s if n_hs else mu_hc
            as_season = as_s if n_as else mu_as
            ac_season = ac_s if n_as else mu_ac

            hs = shrink(
                blend(hs_l, hs_season, last_weight),
                n_hl,
                mu_hs,
                shrink_k,
            )
            hc = shrink(
                blend(hc_l, hc_season, last_weight),
                n_hl,
                mu_hc,
                shrink_k,
            )
            as_ = shrink(
                blend(as_l, as_season, last_weight),
                n_al,
                mu_as,
                shrink_k,
            )
            ac = shrink(
                blend(ac_l, ac_season, last_weight),
                n_al,
                mu_ac,
                shrink_k,
            )
            lam_h = max((hs + ac) / 2.0, 0.0)
            lam_a = max((as_ + hc) / 2.0, 0.0)
            row = BacktestRow(
                fixture_id=fixture.pk,
                league_api_id=league_api,
                season=fixture.season,
                country=league.country,
                league_name=league.name,
                total_goals=gh + ga,
                p_over_15=p_over(lam_h, lam_a, 1.5),
                p_over_25=p_over(lam_h, lam_a, 2.5),
                p_over_35=p_over(lam_h, lam_a, 3.5),
                lambda_total=lam_h + lam_a,
            )

        # Update histories AFTER forecasting (no leakage).
        home_hist[home_id].append((float(gh), float(ga)))
        away_hist[away_id].append((float(ga), float(gh)))
        home_league[(home_id, league_id)].append(
            (float(gh), float(ga)),
        )
        away_league[(away_id, league_id)].append(
            (float(ga), float(gh)),
        )
        league_hist[league_id].append((gh, ga))

        yield row, fixture.season, league_api


def run_backtest(
    *,
    season: int | None = None,
    league_api_id: int | None = None,
    limit: int | None = None,
) -> BacktestReport:
    """Load finished fixtures and run walk-forward.

    Season/league filters apply to scored rows only;
    earlier matches still feed venue/league histories.
    """
    qs = (
        Fixture.objects.filter(
            status__in=FINISHED,
            goals_home__isnull=False,
            goals_away__isnull=False,
        )
        .select_related("league", "home", "away")
        .order_by("kickoff_at", "pk")
    )
    if limit is not None:
        qs = qs[:limit]

    report = BacktestReport()
    for row, row_season, row_league in iter_backtest_rows(
        qs.iterator(chunk_size=2000),
    ):
        if season is not None and row_season != season:
            continue
        if league_api_id is not None and row_league != league_api_id:
            continue
        report.considered += 1
        if row is None:
            report.skipped += 1
            continue
        report.rows.append(row)
    return report


DEFAULT_THRESHOLDS = {
    "o15": [0.70, 0.75, 0.80, 0.82, 0.85, 0.88, 0.90],
    "o25": [0.45, 0.50, 0.55, 0.58, 0.60, 0.65, 0.70],
    "o35": [0.28, 0.32, 0.36, 0.40, 0.42, 0.45, 0.50],
}


def format_report(report: BacktestReport) -> str:
    """Human-readable calibration text."""
    lines: list[str] = []
    n = len(report.rows)
    lines.append("=== OverPick backtest (poisson_v1) ===")
    lines.append(
        f"considered={report.considered} "
        f"scored={n} skipped_form={report.skipped}",
    )
    if n == 0:
        lines.append("No rows to analyse.")
        return "\n".join(lines)

    base = report.base_rates()
    lines.append("")
    lines.append("Base rates (all scored rows):")
    lines.append(
        f"  O1.5={base['o15']:.1%}  "
        f"O2.5={base['o25']:.1%}  "
        f"O3.5={base['o35']:.1%}",
    )
    avg15 = sum(r.p_over_15 for r in report.rows) / n
    avg25 = sum(r.p_over_25 for r in report.rows) / n
    avg35 = sum(r.p_over_35 for r in report.rows) / n
    lines.append(
        f"Mean P: O1.5={avg15:.1%}  O2.5={avg25:.1%}  O3.5={avg35:.1%}",
    )

    lines.append("")
    lines.append("By season (O2.5 base vs mean P):")
    for row in report.by_season("o25"):
        lines.append(
            f"  {row['season']}: n={row['n']} "
            f"base={row['base']:.1%} "
            f"avg_p={row['avg_p']:.1%}",
        )

    for market, label in (
        ("o15", "O1.5"),
        ("o25", "O2.5"),
        ("o35", "O3.5"),
    ):
        lines.append("")
        lines.append(f"Reliability bins {label}:")
        lines.append("  bin       n   avg_p   freq")
        for b in report.reliability_bins(market):
            lines.append(
                f"  {b['bin']:<8} {b['n']:>5} "
                f"{b['avg_p']:>6.1%} "
                f"{b['freq']:>6.1%}",
            )

        lines.append("")
        lines.append(f"Threshold grid {label}:")
        lines.append(
            "  thr    signals   hits   hit_rate  coverage",
        )
        total = n
        for tr in report.threshold_grid(
            market,
            DEFAULT_THRESHOLDS[market],
        ):
            rate = f"{tr.hit_rate:.1%}" if tr.hit_rate is not None else "  —  "
            cov = tr.signals / total if total else 0.0
            lines.append(
                f"  {tr.threshold:.2f}  "
                f"{tr.signals:>7} "
                f"{tr.hits:>6}   {rate:>7}  "
                f"{cov:>7.1%}",
            )

    lines.append("")
    lines.append(
        "Tip: pick the lowest thr where hit_rate is "
        "acceptable and coverage is not tiny.",
    )
    return "\n".join(lines)
