"""Walk-forward GBM prototype vs poisson_v4 (O2.5).

Builds tabular features from the same in-memory histories as
the Poisson backtest (no leakage), then trains an expanding
seasonal GBM. Poisson P is always a feature (residual-style).
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from django.conf import settings

from apps.leagues.competitions import is_uefa_cup
from apps.matches.models import Fixture
from apps.predictions.services.backtest import (
    FINISHED,
    _league_mu,
    _mean_pair,
    _mean_pair_decay,
)
from apps.predictions.services.form import (
    blend,
    lambdas_from_rates,
    shrink,
)
from apps.predictions.services.gbm_features import FEATURE_NAMES
from apps.predictions.services.poisson import p_btts, p_over
from apps.predictions.services.prob_calibration import calibrate_o25


@dataclass
class MlRow:
    """One pre-match feature vector + Poisson P + label."""

    fixture_id: int
    kickoff_at: datetime
    season: int
    league_api_id: int
    hit_25: bool
    p_pois_25: float
    features: dict[str, float]


@dataclass
class ModelScores:
    """Probabilities and tip metrics for one model."""

    name: str
    n: int
    brier: float
    logloss: float
    tip_signals: int
    tip_hits: int
    tip_rate: float | None
    tip_coverage: float
    # Fair compare: same tip count as Poisson baseline.
    iso_hits: int
    iso_rate: float | None


@dataclass
class PrototypeReport:
    """Aggregate walk-forward comparison."""

    n_rows: int
    n_scored: int
    seasons_tested: list[int]
    models: list[ModelScores]
    notes: list[str]


def _o25_rate(
    samples: list[tuple[datetime, float, float, int]],
    *,
    limit: int = 5,
    default: float = 0.5,
) -> float:
    chunk = samples[-limit:] if samples else []
    if not chunk:
        return default
    hits = sum(1 for _, s, c, _ in chunk if (s + c) >= 3.0)
    return hits / len(chunk)


def _league_o25_rate(
    samples: list[tuple[int, int]],
    *,
    limit: int = 40,
    default: float = 0.5,
) -> float:
    chunk = samples[-limit:] if samples else []
    if not chunk:
        return default
    hits = sum(1 for gh, ga in chunk if (gh + ga) >= 3)
    return hits / len(chunk)


def iter_ml_rows(
    fixtures: Iterable[Fixture],
    *,
    n: int | None = None,
    min_n: int | None = None,
    shrink_k: float | None = None,
    last_weight: float | None = None,
) -> Iterator[MlRow]:
    """Yield ML rows; histories updated only after each forecast."""
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
        else float(getattr(settings, "MODEL_LAST_WEIGHT", 0.6))
    )
    half_life = float(
        getattr(settings, "MODEL_DECAY_HALFLIFE_DAYS", 90.0),
    )

    home_league: dict[
        tuple[int, int],
        list[tuple[datetime, float, float, int]],
    ] = defaultdict(list)
    away_league: dict[
        tuple[int, int],
        list[tuple[datetime, float, float, int]],
    ] = defaultdict(list)
    home_any: dict[
        int,
        list[tuple[datetime, float, float, int]],
    ] = defaultdict(list)
    away_any: dict[
        int,
        list[tuple[datetime, float, float, int]],
    ] = defaultdict(list)
    last_any: dict[int, datetime] = {}
    league_hist: dict[int, list[tuple[int, int]]] = defaultdict(list)

    for fixture in fixtures:
        home_id = fixture.home_id
        away_id = fixture.away_id
        league_id = fixture.league_id
        gh = int(fixture.goals_home)
        ga = int(fixture.goals_away)
        kick = fixture.kickoff_at
        league = fixture.league
        league_api = league.api_id

        if is_uefa_cup(league_api):
            home_samples = home_any[home_id]
            away_samples = away_any[away_id]
        else:
            home_samples = home_league[(home_id, league_id)]
            away_samples = away_league[(away_id, league_id)]
        n_hl = min(len(home_samples), n)
        n_al = min(len(away_samples), n)
        enough = n_hl >= min_n and n_al >= min_n

        if enough:
            mu_hs, mu_as = _league_mu(league_hist[league_id])
            mu_hc, mu_ac = mu_as, mu_hs
            hs_l, hc_l, n_hl = _mean_pair_decay(
                home_samples,
                as_of=kick,
                limit=n,
                half_life_days=half_life,
            )
            as_l, ac_l, n_al = _mean_pair_decay(
                away_samples,
                as_of=kick,
                limit=n,
                half_life_days=half_life,
            )
            hs_s, hc_s, n_hs = _mean_pair(home_samples)
            as_s, ac_s, n_as = _mean_pair(away_samples)
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
            lam_h, lam_a = lambdas_from_rates(
                hs,
                hc,
                as_,
                ac,
                mu_hs,
                mu_as,
            )
            p15 = p_over(lam_h, lam_a, 1.5)
            p25 = p_over(lam_h, lam_a, 2.5)
            p35 = p_over(lam_h, lam_a, 3.5)
            pb = p_btts(lam_h, lam_a)

            rest_h = _rest_days_from_last(last_any.get(home_id), kick)
            rest_a = _rest_days_from_last(last_any.get(away_id), kick)

            feats = {
                "p_pois_25": p25,
                "p_pois_15": p15,
                "p_pois_35": p35,
                "p_btts": pb,
                "lambda_total": lam_h + lam_a,
                "hs": hs,
                "hc": hc,
                "as_": as_,
                "ac": ac,
                "mu_hs": mu_hs,
                "mu_as": mu_as,
                "n_home": float(n_hl),
                "n_away": float(n_al),
                "rest_home": rest_h,
                "rest_away": rest_a,
                "home_o25_rate": _o25_rate(home_samples),
                "away_o25_rate": _o25_rate(away_samples),
                "league_o25_rate": _league_o25_rate(
                    league_hist[league_id],
                ),
                "league_api_id": float(league_api),
            }
            yield MlRow(
                fixture_id=fixture.pk,
                kickoff_at=kick,
                season=fixture.season,
                league_api_id=league_api,
                hit_25=(gh + ga) >= 3,
                p_pois_25=p25,
                features=feats,
            )

        home_league[(home_id, league_id)].append(
            (kick, float(gh), float(ga), away_id),
        )
        away_league[(away_id, league_id)].append(
            (kick, float(ga), float(gh), home_id),
        )
        home_any[home_id].append(
            (kick, float(gh), float(ga), away_id),
        )
        away_any[away_id].append(
            (kick, float(ga), float(gh), home_id),
        )
        last_any[home_id] = kick
        last_any[away_id] = kick
        league_hist[league_id].append((gh, ga))


def _rest_days_from_last(
    last: datetime | None,
    as_of: datetime,
    *,
    default: float = 14.0,
) -> float:
    if last is None:
        return default
    return max(0.0, (as_of - last).total_seconds() / 86400.0)


def collect_ml_rows(*, limit: int | None = None) -> list[MlRow]:
    """Load finished fixtures and build ML feature rows."""
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
    return list(iter_ml_rows(qs.iterator(chunk_size=2000)))


def _matrix(rows: list[MlRow]) -> tuple[list[list[float]], list[int]]:
    x = [[float(r.features[name]) for name in FEATURE_NAMES] for r in rows]
    y = [1 if r.hit_25 else 0 for r in rows]
    return x, y


def _brier(probs: list[float], y: list[int]) -> float:
    n = len(y)
    if n == 0:
        return 0.0
    return sum((p - t) ** 2 for p, t in zip(probs, y, strict=True)) / n


def _logloss(probs: list[float], y: list[int]) -> float:
    n = len(y)
    if n == 0:
        return 0.0
    eps = 1e-7
    total = 0.0
    for p, t in zip(probs, y, strict=True):
        p = min(1.0 - eps, max(eps, p))
        total += -(t * math.log(p) + (1 - t) * math.log(1.0 - p))
    return total / n


def _tip_stats(
    probs: list[float],
    y: list[int],
    *,
    thr: float,
) -> tuple[int, int, float | None, float]:
    signals = 0
    hits = 0
    for p, t in zip(probs, y, strict=True):
        if p >= thr:
            signals += 1
            hits += t
    rate = hits / signals if signals else None
    cov = signals / len(y) if y else 0.0
    return signals, hits, rate, cov


def _iso_top_k(
    probs: list[float],
    y: list[int],
    *,
    k: int,
) -> tuple[int, float | None]:
    """Hit rate among top-k probabilities (fair volume)."""
    if k <= 0 or not y:
        return 0, None
    k = min(k, len(y))
    order = sorted(
        range(len(probs)),
        key=lambda i: probs[i],
        reverse=True,
    )[:k]
    hits = sum(y[i] for i in order)
    return hits, hits / k


def _fit_predict_gbm(
    x_train: list[list[float]],
    y_train: list[int],
    x_test: list[list[float]],
) -> tuple[list[float], str]:
    """Train GBM; prefer LightGBM, else sklearn HGB."""
    cat_idx = FEATURE_NAMES.index("league_api_id")
    try:
        import lightgbm as lgb

        model = lgb.LGBMClassifier(
            n_estimators=250,
            learning_rate=0.05,
            num_leaves=31,
            min_child_samples=40,
            subsample=0.85,
            colsample_bytree=0.85,
            reg_lambda=1.0,
            random_state=42,
            verbosity=-1,
            n_jobs=2,
        )
        model.fit(
            x_train,
            y_train,
            categorical_feature=[cat_idx],
        )
        proba = model.predict_proba(x_test)[:, 1]
        return [float(p) for p in proba], "lightgbm"
    except Exception:
        from sklearn.ensemble import HistGradientBoostingClassifier

        model = HistGradientBoostingClassifier(
            max_iter=250,
            learning_rate=0.05,
            max_leaf_nodes=31,
            min_samples_leaf=40,
            l2_regularization=1.0,
            random_state=42,
            categorical_features=[cat_idx],
        )
        model.fit(x_train, y_train)
        proba = model.predict_proba(x_test)[:, 1]
        return [float(p) for p in proba], "sklearn_hgb"


def run_gbm_prototype(
    *,
    limit: int | None = None,
    min_train: int = 8000,
    pois_thr: float | None = None,
    gbm_thr: float = 0.60,
    hybrid_thr: float = 0.60,
) -> PrototypeReport:
    """Expanding-season walk-forward: Poisson vs GBM vs hybrid."""
    if pois_thr is None:
        pois_thr = float(settings.SIGNAL_THRESHOLD_O25)

    rows = collect_ml_rows(limit=limit)
    notes: list[str] = []
    if not rows:
        return PrototypeReport(
            n_rows=0,
            n_scored=0,
            seasons_tested=[],
            models=[],
            notes=["No ML rows (empty DB or insufficient form)."],
        )

    seasons = sorted({r.season for r in rows})
    by_season: dict[int, list[MlRow]] = defaultdict(list)
    for r in rows:
        by_season[r.season].append(r)

    y_all: list[int] = []
    p_pois: list[float] = []
    p_pois_cal: list[float] = []
    p_gbm: list[float] = []
    p_hybrid: list[float] = []
    tested_seasons: list[int] = []
    backend = ""

    train_pool: list[MlRow] = []
    for season in seasons:
        test_rows = by_season[season]
        if len(train_pool) < min_train:
            notes.append(
                f"season {season}: train-only "
                f"(pool {len(train_pool)}→"
                f"{len(train_pool) + len(test_rows)}, "
                f"need ≥{min_train})",
            )
            train_pool.extend(test_rows)
            continue

        x_tr, y_tr = _matrix(train_pool)
        x_te, y_te = _matrix(test_rows)
        gbm_probs, backend = _fit_predict_gbm(x_tr, y_tr, x_te)

        for row, gp in zip(test_rows, gbm_probs, strict=True):
            pc = calibrate_o25(row.p_pois_25)
            # Residual GBM already saw raw Poisson P.
            hyb = 0.5 * pc + 0.5 * gp
            y_all.append(1 if row.hit_25 else 0)
            p_pois.append(row.p_pois_25)
            p_pois_cal.append(pc)
            p_gbm.append(gp)
            p_hybrid.append(hyb)

        tested_seasons.append(season)
        train_pool.extend(test_rows)

    if not y_all:
        return PrototypeReport(
            n_rows=len(rows),
            n_scored=0,
            seasons_tested=[],
            models=[],
            notes=notes + ["No seasons left after min_train gate."],
        )

    notes.append(f"GBM backend: {backend or 'n/a'}")
    notes.append(
        f"Features: {', '.join(FEATURE_NAMES)}",
    )

    # Baseline tip count from calibrated Poisson @ product thr.
    base_signals, _, _, _ = _tip_stats(
        p_pois_cal,
        y_all,
        thr=pois_thr,
    )

    def pack(
        name: str,
        probs: list[float],
        thr: float,
    ) -> ModelScores:
        brier = _brier(probs, y_all)
        ll = _logloss(probs, y_all)
        sig, hits, rate, cov = _tip_stats(probs, y_all, thr=thr)
        iso_hits, iso_rate = _iso_top_k(
            probs,
            y_all,
            k=base_signals,
        )
        return ModelScores(
            name=name,
            n=len(y_all),
            brier=brier,
            logloss=ll,
            tip_signals=sig,
            tip_hits=hits,
            tip_rate=rate,
            tip_coverage=cov,
            iso_hits=iso_hits,
            iso_rate=iso_rate,
        )

    # Dual-filter hybrid: both models above thr.
    dual_probs: list[float] = []
    for pc, gp in zip(p_pois_cal, p_gbm, strict=True):
        if pc >= pois_thr and gp >= gbm_thr:
            dual_probs.append(max(pc, gp))
        else:
            dual_probs.append(0.0)

    models = [
        pack("poisson_raw", p_pois, thr=0.65),
        pack(f"poisson_cal@{pois_thr:.2f}", p_pois_cal, thr=pois_thr),
        pack(f"gbm@{gbm_thr:.2f}", p_gbm, thr=gbm_thr),
        pack(
            f"hybrid_avg@{hybrid_thr:.2f}",
            p_hybrid,
            thr=hybrid_thr,
        ),
        pack(
            f"hybrid_and@{pois_thr:.2f}/{gbm_thr:.2f}",
            dual_probs,
            thr=0.5,
        ),
    ]

    return PrototypeReport(
        n_rows=len(rows),
        n_scored=len(y_all),
        seasons_tested=tested_seasons,
        models=models,
        notes=notes,
    )


def format_prototype_report(report: PrototypeReport) -> str:
    """Human-readable comparison table."""
    lines: list[str] = [
        "GBM prototype (walk-forward by season)",
        f"rows_total={report.n_rows}  scored={report.n_scored}",
        f"seasons_tested={report.seasons_tested}",
        "",
        f"{'model':<28} {'brier':>7} {'logloss':>8} "
        f"{'tips':>6} {'hit%':>7} {'cov':>6} "
        f"{'iso_hit%':>8}",
        "-" * 80,
    ]
    for m in report.models:
        hit = f"{m.tip_rate:.1%}" if m.tip_rate is not None else "  —  "
        iso = f"{m.iso_rate:.1%}" if m.iso_rate is not None else "  —  "
        lines.append(
            f"{m.name:<28} {m.brier:7.4f} {m.logloss:8.4f} "
            f"{m.tip_signals:6d} {hit:>7} {m.tip_coverage:6.1%} "
            f"{iso:>8}",
        )
    lines.append("")
    lines.append(
        "iso_hit% = hit rate among top-N probs, "
        "N = poisson_cal tip count (fair volume).",
    )
    lines.append(
        "hybrid_avg = 0.5*P_cal + 0.5*P_gbm; "
        "hybrid_and = tip only if both ≥ thr.",
    )
    if report.notes:
        lines.append("")
        lines.append("Notes:")
        for note in report.notes:
            lines.append(f"  - {note}")
    return "\n".join(lines)


def feature_importance_proxy(rows: list[MlRow]) -> dict[str, Any]:
    """Optional: single full-fit importances (debug, not walk-forward)."""
    if len(rows) < 500:
        return {}
    split = int(len(rows) * 0.8)
    x_tr, y_tr = _matrix(rows[:split])
    x_te, _y_te = _matrix(rows[split:])
    try:
        import lightgbm as lgb

        model = lgb.LGBMClassifier(
            n_estimators=200,
            learning_rate=0.05,
            num_leaves=31,
            random_state=42,
            verbosity=-1,
        )
        cat_idx = FEATURE_NAMES.index("league_api_id")
        model.fit(x_tr, y_tr, categorical_feature=[cat_idx])
        imp = model.feature_importances_
        return {
            name: float(v)
            for name, v in sorted(
                zip(FEATURE_NAMES, imp, strict=True),
                key=lambda t: -t[1],
            )
        }
    except Exception:
        return {}
