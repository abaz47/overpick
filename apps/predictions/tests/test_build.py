"""Tests for form + build_predictions."""

from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.leagues.models import League, Team
from apps.matches.models import Fixture
from apps.predictions.models import Prediction
from apps.predictions.services.build import (
    build_predictions,
    predict_fixture,
)
from apps.predictions.services.form import (
    build_form_features,
    expected_goals,
)


def _league() -> League:
    return League.objects.create(
        api_id=39,
        name="Premier League",
        country="England",
        code="PL",
        season=2026,
    )


def _team(api_id: int, name: str) -> Team:
    return Team.objects.create(api_id=api_id, name=name)


def _finished(
    *,
    league: League,
    home: Team,
    away: Team,
    kickoff,
    gh: int,
    ga: int,
    api_id: int,
) -> Fixture:
    return Fixture.objects.create(
        api_id=api_id,
        league=league,
        season=league.season,
        home=home,
        away=away,
        kickoff_at=kickoff,
        status=Fixture.Status.FT,
        goals_home=gh,
        goals_away=ga,
    )


@pytest.mark.django_db
def test_predict_fixture_creates_locked_row() -> None:
    league = _league()
    home = _team(1, "Home FC")
    away = _team(2, "Away FC")
    filler = _team(3, "Filler")
    now = timezone.now()
    # Last home games for home team.
    for i in range(5):
        _finished(
            league=league,
            home=home,
            away=filler,
            kickoff=now - timedelta(days=30 - i),
            gh=2,
            ga=1,
            api_id=1000 + i,
        )
    # Last away games for away team.
    for i in range(5):
        _finished(
            league=league,
            home=filler,
            away=away,
            kickoff=now - timedelta(days=20 - i),
            gh=1,
            ga=2,
            api_id=2000 + i,
        )
    upcoming = Fixture.objects.create(
        api_id=9001,
        league=league,
        season=league.season,
        home=home,
        away=away,
        kickoff_at=now + timedelta(days=1),
        status=Fixture.Status.NS,
    )
    features = build_form_features(upcoming)
    assert features.enough_data is True
    lam_h, lam_a = expected_goals(features)
    assert lam_h > 0 and lam_a > 0

    pred = predict_fixture(upcoming)
    assert pred.is_locked is True
    assert pred.lambda_total == pytest.approx(
        pred.lambda_home + pred.lambda_away,
    )
    assert 0 < pred.p_over_15 <= 1
    assert pred.p_over_15 >= pred.p_over_25 >= pred.p_over_35
    assert "signals" in pred.features_json


@pytest.mark.django_db
def test_build_skips_locked_and_insufficient() -> None:
    from apps.predictions.services.batch import (
        current_batch_window,
    )

    league = _league()
    home = _team(10, "H")
    away = _team(11, "A")
    start, end = current_batch_window()
    kick = min(
        timezone.now() + timedelta(hours=3),
        end - timedelta(minutes=30),
    )
    if kick < start:
        kick = start + timedelta(hours=1)
    upcoming = Fixture.objects.create(
        api_id=9002,
        league=league,
        season=league.season,
        home=home,
        away=away,
        kickoff_at=kick,
        status=Fixture.Status.NS,
    )
    stats = build_predictions()
    assert stats.considered == 1
    assert stats.skipped_form == 1
    assert Prediction.objects.count() == 0

    # Not enough history → still skipped.
    call_command("build_predictions")
    assert (
        Prediction.objects.filter(
            fixture=upcoming,
        ).count()
        == 0
    )
