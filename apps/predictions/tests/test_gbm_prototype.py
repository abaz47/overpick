"""Smoke tests for GBM prototype helpers."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.leagues.models import League, Team
from apps.matches.models import Fixture
from apps.predictions.services.gbm_features import FEATURE_NAMES
from apps.predictions.services.gbm_prototype import (
    collect_ml_rows,
    format_prototype_report,
    run_gbm_prototype,
)


def _league() -> League:
    return League.objects.create(
        api_id=39,
        name="Premier League",
        country="England",
        code="PL",
        season=2024,
    )


def _team(api_id: int, name: str) -> Team:
    return Team.objects.create(api_id=api_id, name=name)


def _ft(
    *,
    league: League,
    home: Team,
    away: Team,
    kickoff,
    gh: int,
    ga: int,
    api_id: int,
    season: int | None = None,
) -> Fixture:
    return Fixture.objects.create(
        api_id=api_id,
        league=league,
        season=season if season is not None else league.season,
        home=home,
        away=away,
        kickoff_at=kickoff,
        status=Fixture.Status.FT,
        goals_home=gh,
        goals_away=ga,
    )


@pytest.mark.django_db
def test_collect_ml_rows_has_features() -> None:
    league = _league()
    home = _team(1, "Home FC")
    away = _team(2, "Away FC")
    filler = _team(3, "Filler")
    now = timezone.now()
    api = 1000
    for i in range(5):
        _ft(
            league=league,
            home=home,
            away=filler,
            kickoff=now - timedelta(days=60 - i),
            gh=2,
            ga=1,
            api_id=api,
        )
        api += 1
        _ft(
            league=league,
            home=filler,
            away=away,
            kickoff=now - timedelta(days=50 - i),
            gh=1,
            ga=2,
            api_id=api,
        )
        api += 1
    _ft(
        league=league,
        home=home,
        away=away,
        kickoff=now,
        gh=2,
        ga=2,
        api_id=api,
    )
    rows = collect_ml_rows()
    assert rows
    assert set(rows[0].features) == set(FEATURE_NAMES)
    assert rows[-1].hit_25 is True


@pytest.mark.django_db
def test_run_prototype_empty_enough_for_format() -> None:
    report = run_gbm_prototype(min_train=10)
    text = format_prototype_report(report)
    assert "GBM prototype" in text
