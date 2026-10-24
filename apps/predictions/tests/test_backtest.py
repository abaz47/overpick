"""Tests for walk-forward backtest."""

from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.leagues.models import League, Team
from apps.matches.models import Fixture
from apps.predictions.services.backtest import (
    format_report,
    run_backtest,
)
from apps.predictions.services.form import (
    build_form_features,
    expected_goals,
)
from apps.predictions.services.poisson import p_btts, p_over


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


def _ft(
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
def test_backtest_matches_orm_form() -> None:
    """In-memory walk-forward ≈ ORM form+poisson."""
    league = _league()
    home = _team(1, "Home FC")
    away = _team(2, "Away FC")
    filler = _team(3, "Filler")
    now = timezone.now()
    for i in range(5):
        _ft(
            league=league,
            home=home,
            away=filler,
            kickoff=now - timedelta(days=40 - i),
            gh=2,
            ga=1,
            api_id=1000 + i,
        )
    for i in range(5):
        _ft(
            league=league,
            home=filler,
            away=away,
            kickoff=now - timedelta(days=30 - i),
            gh=1,
            ga=1,
            api_id=2000 + i,
        )
    target = _ft(
        league=league,
        home=home,
        away=away,
        kickoff=now - timedelta(days=1),
        gh=3,
        ga=1,
        api_id=3000,
    )

    report = run_backtest()
    scored = [r for r in report.rows if r.fixture_id == target.pk]
    assert len(scored) == 1
    row = scored[0]

    feats = build_form_features(target)
    lam_h, lam_a = expected_goals(feats)
    assert abs(row.p_over_25 - p_over(lam_h, lam_a, 2.5)) < 1e-9
    assert abs(row.p_btts - p_btts(lam_h, lam_a)) < 1e-9
    assert row.hit_25 is True
    assert row.hit_btts is True


@pytest.mark.django_db
def test_backtest_command_writes_report(tmp_path) -> None:
    league = _league()
    a = _team(1, "A")
    b = _team(2, "B")
    c = _team(3, "C")
    now = timezone.now()
    for i in range(4):
        _ft(
            league=league,
            home=a,
            away=c,
            kickoff=now - timedelta(days=20 - i),
            gh=2,
            ga=0,
            api_id=10 + i,
        )
        _ft(
            league=league,
            home=c,
            away=b,
            kickoff=now - timedelta(days=19 - i),
            gh=1,
            ga=2,
            api_id=20 + i,
        )
    _ft(
        league=league,
        home=a,
        away=b,
        kickoff=now - timedelta(days=1),
        gh=2,
        ga=2,
        api_id=99,
    )
    out = tmp_path / "bt.txt"
    call_command("backtest_predictions", output=str(out))
    text = out.read_text(encoding="utf-8")
    assert "Threshold grid" in text
    assert "scored=" in text


@pytest.mark.django_db
def test_format_report_empty() -> None:
    text = format_report(run_backtest())
    assert "No rows" in text or "scored=0" in text
