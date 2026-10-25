"""Tabular features for O2.5 GBM (aligned with walk-forward prototype)."""

from __future__ import annotations

from datetime import datetime

from django.db.models import Q

from apps.leagues.competitions import form_league_scope
from apps.matches.models import Fixture
from apps.predictions.services.form import (
    FormFeatures,
    finished_qs,
)

FEATURE_NAMES = (
    "p_pois_25",
    "p_pois_15",
    "p_pois_35",
    "p_btts",
    "lambda_total",
    "hs",
    "hc",
    "as_",
    "ac",
    "mu_hs",
    "mu_as",
    "n_home",
    "n_away",
    "rest_home",
    "rest_away",
    "home_o25_rate",
    "away_o25_rate",
    "league_o25_rate",
    "league_api_id",
)

HYBRID_WEIGHT_GBM = 0.5


def feature_vector(feats: dict[str, float]) -> list[float]:
    """Ordered float vector for GBM."""
    return [float(feats[name]) for name in FEATURE_NAMES]


def team_rest_days(team_id: int, before: datetime) -> float:
    """Days since team's last finished match (any competition)."""
    last = (
        finished_qs(before)
        .filter(Q(home_id=team_id) | Q(away_id=team_id))
        .order_by("-kickoff_at")
        .values_list("kickoff_at", flat=True)
        .first()
    )
    if last is None:
        return 14.0
    return max(0.0, (before - last).total_seconds() / 86400.0)


def venue_o25_rate(
    team_id: int,
    *,
    home: bool,
    before: datetime,
    league_id: int | None,
    limit: int = 5,
) -> float:
    """Share of last-N venue matches with total goals ≥ 3."""
    qs = finished_qs(before)
    qs = qs.filter(home_id=team_id) if home else qs.filter(away_id=team_id)
    if league_id is not None:
        qs = qs.filter(league_id=league_id)
    rows = list(
        qs.order_by("-kickoff_at").values_list(
            "goals_home",
            "goals_away",
        )[:limit],
    )
    if not rows:
        return 0.5
    hits = sum(1 for gh, ga in rows if (gh + ga) >= 3)
    return hits / len(rows)


def league_o25_rate(
    league_id: int,
    before: datetime,
    *,
    limit: int = 40,
) -> float:
    """Recent league O2.5 frequency."""
    rows = list(
        finished_qs(before)
        .filter(league_id=league_id)
        .order_by("-kickoff_at")
        .values_list("goals_home", "goals_away")[:limit],
    )
    if not rows:
        return 0.5
    hits = sum(1 for gh, ga in rows if (gh + ga) >= 3)
    return hits / len(rows)


def build_gbm_feature_dict(
    fixture: Fixture,
    form: FormFeatures,
    *,
    p15: float,
    p25: float,
    p35: float,
    p_btts: float,
    lambda_home: float,
    lambda_away: float,
) -> dict[str, float]:
    """Pre-match feature dict matching FEATURE_NAMES."""
    before = fixture.kickoff_at
    league_id = fixture.league_id
    league_api = fixture.league.api_id if fixture.league_id else 0
    form_league_id = form_league_scope(league_id, league_api)
    return {
        "p_pois_25": float(p25),
        "p_pois_15": float(p15),
        "p_pois_35": float(p35),
        "p_btts": float(p_btts),
        "lambda_total": float(lambda_home + lambda_away),
        "hs": float(form.hs),
        "hc": float(form.hc),
        "as_": float(form.as_),
        "ac": float(form.ac),
        "mu_hs": float(form.league_mu_home_scored),
        "mu_as": float(form.league_mu_away_scored),
        "n_home": float(form.home_last.sample_size),
        "n_away": float(form.away_last.sample_size),
        "rest_home": team_rest_days(fixture.home_id, before),
        "rest_away": team_rest_days(fixture.away_id, before),
        "home_o25_rate": venue_o25_rate(
            fixture.home_id,
            home=True,
            before=before,
            league_id=form_league_id,
        ),
        "away_o25_rate": venue_o25_rate(
            fixture.away_id,
            home=False,
            before=before,
            league_id=form_league_id,
        ),
        "league_o25_rate": league_o25_rate(league_id, before),
        "league_api_id": float(league_api),
    }


def hybrid_probability(p_cal: float, p_gbm: float) -> float:
    """Blend calibrated Poisson with GBM."""
    w = HYBRID_WEIGHT_GBM
    return (1.0 - w) * float(p_cal) + w * float(p_gbm)
