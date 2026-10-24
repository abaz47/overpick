"""Venue form and league averages for Poisson v1."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime

from django.conf import settings
from django.db.models import Avg, QuerySet

from apps.leagues.models import Team
from apps.matches.models import Fixture

FINISHED = (
    Fixture.Status.FT,
    Fixture.Status.AET,
    Fixture.Status.PEN,
)


@dataclass
class VenueRates:
    """Average scored / conceded in a venue role."""

    scored: float
    conceded: float
    sample_size: int


@dataclass
class FormFeatures:
    """Inputs stored on Prediction.features_json."""

    n: int
    min_n: int
    shrink_k: float
    last_weight: float
    home_last: VenueRates
    away_last: VenueRates
    home_season: VenueRates
    away_season: VenueRates
    league_mu_home_scored: float
    league_mu_away_scored: float
    hs: float
    hc: float
    as_: float
    ac: float
    enough_data: bool

    def to_json(self) -> dict:
        """JSON-serializable dict (as_ is renamed)."""
        data = asdict(self)
        data["as"] = data.pop("as_")
        return data


def finished_qs(before: datetime) -> QuerySet[Fixture]:
    """Finished matches with scores before a kickoff."""
    return Fixture.objects.filter(
        status__in=FINISHED,
        kickoff_at__lt=before,
        goals_home__isnull=False,
        goals_away__isnull=False,
    )


def team_venue_rates(
    team: Team,
    *,
    home: bool,
    before: datetime,
    limit: int | None = None,
    league_id: int | None = None,
) -> VenueRates:
    """Mean scored/conceded for a team in home or away."""
    qs = finished_qs(before)
    if home:
        qs = qs.filter(home=team)
        scored_field = "goals_home"
        conceded_field = "goals_away"
    else:
        qs = qs.filter(away=team)
        scored_field = "goals_away"
        conceded_field = "goals_home"
    if league_id is not None:
        qs = qs.filter(league_id=league_id)
    qs = qs.order_by("-kickoff_at")
    if limit is not None:
        ids = list(qs.values_list("pk", flat=True)[:limit])
        qs = Fixture.objects.filter(pk__in=ids)
    agg = qs.aggregate(
        scored=Avg(scored_field),
        conceded=Avg(conceded_field),
    )
    n = qs.count()
    if n == 0:
        return VenueRates(0.0, 0.0, 0)
    return VenueRates(
        float(agg["scored"] or 0.0),
        float(agg["conceded"] or 0.0),
        n,
    )


def league_means(
    league_id: int,
    before: datetime,
) -> tuple[float, float]:
    """League μ home-scored and μ away-scored before date."""
    qs = finished_qs(before).filter(league_id=league_id)
    agg = qs.aggregate(
        hs=Avg("goals_home"),
        as_=Avg("goals_away"),
    )
    # Fallback to a neutral prior if league empty.
    mu_hs = float(agg["hs"] if agg["hs"] is not None else 1.3)
    mu_as = float(agg["as_"] if agg["as_"] is not None else 1.1)
    return mu_hs, mu_as


def shrink(
    rate: float,
    n: int,
    mu: float,
    k: float,
) -> float:
    """Bayesian-style shrink toward league mean."""
    return (n * rate + k * mu) / (n + k) if n + k else mu


def blend(last: float, season: float, w: float) -> float:
    """Weighted mix of short form and season rate."""
    return w * last + (1.0 - w) * season


def build_form_features(
    fixture: Fixture,
    *,
    n: int | None = None,
    min_n: int | None = None,
    shrink_k: float | None = None,
    last_weight: float | None = None,
) -> FormFeatures:
    """Compute shrunk/blended HS, HC, AS, AC for a fixture."""
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
    before = fixture.kickoff_at
    league_id = fixture.league_id

    home_last = team_venue_rates(
        fixture.home,
        home=True,
        before=before,
        limit=n,
    )
    away_last = team_venue_rates(
        fixture.away,
        home=False,
        before=before,
        limit=n,
    )
    home_season = team_venue_rates(
        fixture.home,
        home=True,
        before=before,
        league_id=league_id,
    )
    away_season = team_venue_rates(
        fixture.away,
        home=False,
        before=before,
        league_id=league_id,
    )
    mu_hs, mu_as = league_means(league_id, before)
    mu_hc, mu_ac = mu_as, mu_hs

    enough = home_last.sample_size >= min_n and away_last.sample_size >= min_n

    hs_season = home_season.scored if home_season.sample_size else mu_hs
    hc_season = home_season.conceded if home_season.sample_size else mu_hc
    as_season = away_season.scored if away_season.sample_size else mu_as
    ac_season = away_season.conceded if away_season.sample_size else mu_ac
    hs_raw = blend(home_last.scored, hs_season, last_weight)
    hc_raw = blend(home_last.conceded, hc_season, last_weight)
    as_raw = blend(away_last.scored, as_season, last_weight)
    ac_raw = blend(away_last.conceded, ac_season, last_weight)

    # Shrink using last-N sample sizes.
    hs = shrink(hs_raw, home_last.sample_size, mu_hs, shrink_k)
    hc = shrink(hc_raw, home_last.sample_size, mu_hc, shrink_k)
    as_ = shrink(as_raw, away_last.sample_size, mu_as, shrink_k)
    ac = shrink(ac_raw, away_last.sample_size, mu_ac, shrink_k)

    return FormFeatures(
        n=n,
        min_n=min_n,
        shrink_k=shrink_k,
        last_weight=last_weight,
        home_last=home_last,
        away_last=away_last,
        home_season=home_season,
        away_season=away_season,
        league_mu_home_scored=mu_hs,
        league_mu_away_scored=mu_as,
        hs=hs,
        hc=hc,
        as_=as_,
        ac=ac,
        enough_data=enough,
    )


def expected_goals(
    features: FormFeatures,
) -> tuple[float, float]:
    """λ_H, λ_A from attack/defence averages."""
    lambda_home = (features.hs + features.ac) / 2.0
    lambda_away = (features.as_ + features.hc) / 2.0
    # Keep lambdas non-negative for Poisson.
    return max(lambda_home, 0.0), max(lambda_away, 0.0)
