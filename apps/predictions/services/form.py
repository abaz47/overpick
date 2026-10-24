"""Venue form with decay and opponent adjustment (poisson_v3)."""

from __future__ import annotations

import math
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

# Floor so weak defences do not explode adjusted goals.
_OPP_RATE_FLOOR = 0.35
# Sanity bounds for attack/defence indices and λ.
_INDEX_MIN = 0.6
_INDEX_MAX = 1.5
_LAMBDA_SIDE_MAX = 2.8
_LAMBDA_TOTAL_MAX = 5.0


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
    decay_halflife_days: float
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
    opponent_adjusted: bool = True

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


def decay_weight(
    as_of: datetime,
    kickoff: datetime,
    half_life_days: float,
) -> float:
    """Exponential decay weight (1 at as_of, 0.5 at half-life)."""
    if half_life_days <= 0:
        return 1.0
    days = max(
        (as_of - kickoff).total_seconds() / 86400.0,
        0.0,
    )
    return math.pow(0.5, days / half_life_days)


def adjust_vs_opponent(
    goals: float,
    opponent_rate: float,
    league_mu: float,
) -> float:
    """Scale goals by opponent strength vs league average.

    Soft defence (high concede rate) → down-weight our scored.
    """
    denom = max(opponent_rate, _OPP_RATE_FLOOR)
    return goals * (league_mu / denom)


def team_venue_rates(
    team: Team,
    *,
    home: bool,
    before: datetime,
    limit: int | None = None,
    league_id: int | None = None,
    half_life_days: float | None = None,
    opponent_adjust: bool = False,
    mu_scored: float | None = None,
    mu_conceded: float | None = None,
) -> VenueRates:
    """Mean scored/conceded for a team in home or away."""
    if half_life_days is None:
        half_life_days = float(
            getattr(settings, "MODEL_DECAY_HALFLIFE_DAYS", 90),
        )
    qs = finished_qs(before)
    qs = qs.filter(home=team) if home else qs.filter(away=team)
    if league_id is not None:
        qs = qs.filter(league_id=league_id)
    qs = qs.order_by("-kickoff_at")

    if limit is not None:
        fixtures = list(
            qs.select_related("home", "away")[:limit],
        )
        return _weighted_venue_rates(
            fixtures,
            home=home,
            as_of=before,
            half_life_days=half_life_days,
            opponent_adjust=opponent_adjust,
            mu_scored=mu_scored,
            mu_conceded=mu_conceded,
            league_id=league_id,
        )

    if home:
        scored_field = "goals_home"
        conceded_field = "goals_away"
    else:
        scored_field = "goals_away"
        conceded_field = "goals_home"
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


def _opp_simple_rate(
    opponent: Team,
    *,
    opponent_at_home: bool,
    before: datetime,
    league_id: int | None,
    want_conceded: bool,
) -> float | None:
    """Cheap season mean for opponent (no decay)."""
    rates = team_venue_rates(
        opponent,
        home=opponent_at_home,
        before=before,
        league_id=league_id,
        half_life_days=0.0,
        opponent_adjust=False,
    )
    if rates.sample_size == 0:
        return None
    return rates.conceded if want_conceded else rates.scored


def _weighted_venue_rates(
    fixtures: list[Fixture],
    *,
    home: bool,
    as_of: datetime,
    half_life_days: float,
    opponent_adjust: bool,
    mu_scored: float | None,
    mu_conceded: float | None,
    league_id: int | None,
) -> VenueRates:
    """Decay-weighted scored/conceded, optional opp adjust."""
    if not fixtures:
        return VenueRates(0.0, 0.0, 0)
    w_sum = 0.0
    scored_sum = 0.0
    conceded_sum = 0.0
    for fx in fixtures:
        if home:
            scored = float(fx.goals_home)
            conceded = float(fx.goals_away)
            opponent = fx.away
            # Opponent was away: their away concede / scored.
            opp_at_home = False
        else:
            scored = float(fx.goals_away)
            conceded = float(fx.goals_home)
            opponent = fx.home
            opp_at_home = True

        if opponent_adjust and mu_scored is not None:
            opp_conc = _opp_simple_rate(
                opponent,
                opponent_at_home=opp_at_home,
                before=fx.kickoff_at,
                league_id=league_id,
                want_conceded=True,
            )
            if opp_conc is not None:
                scored = adjust_vs_opponent(
                    scored,
                    opp_conc,
                    mu_scored,
                )
        if opponent_adjust and mu_conceded is not None:
            opp_att = _opp_simple_rate(
                opponent,
                opponent_at_home=opp_at_home,
                before=fx.kickoff_at,
                league_id=league_id,
                want_conceded=False,
            )
            if opp_att is not None:
                conceded = adjust_vs_opponent(
                    conceded,
                    opp_att,
                    mu_conceded,
                )

        weight = decay_weight(
            as_of,
            fx.kickoff_at,
            half_life_days,
        )
        w_sum += weight
        scored_sum += weight * scored
        conceded_sum += weight * conceded
    if w_sum <= 0:
        return VenueRates(0.0, 0.0, 0)
    return VenueRates(
        scored_sum / w_sum,
        conceded_sum / w_sum,
        len(fixtures),
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
    half_life_days: float | None = None,
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
    half_life_days = (
        half_life_days
        if half_life_days is not None
        else float(
            getattr(
                settings,
                "MODEL_DECAY_HALFLIFE_DAYS",
                90.0,
            ),
        )
    )
    before = fixture.kickoff_at
    league_id = fixture.league_id
    mu_hs, mu_as = league_means(league_id, before)
    mu_hc, mu_ac = mu_as, mu_hs

    # No per-match opponent adjust here: strength vs opponent
    # is applied once in expected_goals (att×def×μ).
    home_last = team_venue_rates(
        fixture.home,
        home=True,
        before=before,
        limit=n,
        half_life_days=half_life_days,
        opponent_adjust=False,
        league_id=league_id,
    )
    away_last = team_venue_rates(
        fixture.away,
        home=False,
        before=before,
        limit=n,
        half_life_days=half_life_days,
        opponent_adjust=False,
        league_id=league_id,
    )
    home_season = team_venue_rates(
        fixture.home,
        home=True,
        before=before,
        league_id=league_id,
        half_life_days=0.0,
    )
    away_season = team_venue_rates(
        fixture.away,
        home=False,
        before=before,
        league_id=league_id,
        half_life_days=0.0,
    )

    enough = home_last.sample_size >= min_n and away_last.sample_size >= min_n

    hs_season = home_season.scored if home_season.sample_size else mu_hs
    hc_season = home_season.conceded if home_season.sample_size else mu_hc
    as_season = away_season.scored if away_season.sample_size else mu_as
    ac_season = away_season.conceded if away_season.sample_size else mu_ac
    hs_raw = blend(home_last.scored, hs_season, last_weight)
    hc_raw = blend(home_last.conceded, hc_season, last_weight)
    as_raw = blend(away_last.scored, as_season, last_weight)
    ac_raw = blend(away_last.conceded, ac_season, last_weight)

    hs = shrink(hs_raw, home_last.sample_size, mu_hs, shrink_k)
    hc = shrink(hc_raw, home_last.sample_size, mu_hc, shrink_k)
    as_ = shrink(as_raw, away_last.sample_size, mu_as, shrink_k)
    ac = shrink(ac_raw, away_last.sample_size, mu_ac, shrink_k)

    return FormFeatures(
        n=n,
        min_n=min_n,
        shrink_k=shrink_k,
        last_weight=last_weight,
        decay_halflife_days=half_life_days,
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
        opponent_adjusted=False,
    )


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def lambdas_from_rates(
    hs: float,
    hc: float,
    as_: float,
    ac: float,
    mu_hs: float,
    mu_as: float,
    *,
    index_min: float | None = None,
    index_max: float | None = None,
    side_max: float | None = None,
    total_max: float | None = None,
) -> tuple[float, float]:
    """λ from attack×defence×league with sanity caps."""
    index_min = (
        index_min
        if index_min is not None
        else float(
            getattr(settings, "MODEL_INDEX_MIN", _INDEX_MIN),
        )
    )
    index_max = (
        index_max
        if index_max is not None
        else float(
            getattr(settings, "MODEL_INDEX_MAX", _INDEX_MAX),
        )
    )
    side_max = (
        side_max
        if side_max is not None
        else float(
            getattr(
                settings,
                "MODEL_LAMBDA_SIDE_MAX",
                _LAMBDA_SIDE_MAX,
            ),
        )
    )
    total_max = (
        total_max
        if total_max is not None
        else float(
            getattr(
                settings,
                "MODEL_LAMBDA_TOTAL_MAX",
                _LAMBDA_TOTAL_MAX,
            ),
        )
    )
    mu_hs = max(mu_hs, _OPP_RATE_FLOOR)
    mu_as = max(mu_as, _OPP_RATE_FLOOR)
    att_home = _clamp(hs / mu_hs, index_min, index_max)
    def_away = _clamp(ac / mu_as, index_min, index_max)
    att_away = _clamp(as_ / mu_as, index_min, index_max)
    def_home = _clamp(hc / mu_hs, index_min, index_max)
    lambda_home = min(
        max(att_home * def_away * mu_hs, 0.0),
        side_max,
    )
    lambda_away = min(
        max(att_away * def_home * mu_as, 0.0),
        side_max,
    )
    total = lambda_home + lambda_away
    if total > total_max and total > 0:
        scale = total_max / total
        lambda_home *= scale
        lambda_away *= scale
    return lambda_home, lambda_away


def expected_goals(
    features: FormFeatures,
) -> tuple[float, float]:
    """λ from attack×defence×league (capped)."""
    return lambdas_from_rates(
        features.hs,
        features.hc,
        features.as_,
        features.ac,
        features.league_mu_home_scored,
        features.league_mu_away_scored,
    )
