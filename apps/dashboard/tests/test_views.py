"""Smoke tests for dashboard pages."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.core.stats_window import (
    site_launch_at,
    today_picks_start,
)
from apps.leagues.models import League, Team
from apps.matches.models import Fixture
from apps.predictions.models import Prediction
from apps.predictions.services.batch import (
    current_batch_window,
    tomorrow_batch_window,
)


def _signals(*, o25: bool = True) -> dict:
    return {
        "o15": False,
        "o25": o25,
        "o35": False,
        "btts": False,
        "primary": "o25" if o25 else None,
        "primary_edge": 0.07 if o25 else None,
    }


@pytest.fixture
def sample_prediction(db):
    league = League.objects.create(
        api_id=39,
        name="Premier League",
        country="England",
        code="PL",
        season=2026,
        is_active=True,
    )
    home = Team.objects.create(api_id=1, name="Home")
    away = Team.objects.create(api_id=2, name="Away")
    start, end = current_batch_window()
    list_start = today_picks_start(start, end)
    kick = list_start + timedelta(hours=2)
    if kick <= timezone.now():
        kick = timezone.now() + timedelta(hours=1)
    if kick >= end:
        kick = max(list_start + timedelta(minutes=30), start)
    fixture = Fixture.objects.create(
        api_id=5001,
        league=league,
        season=2026,
        home=home,
        away=away,
        kickoff_at=kick,
        status=Fixture.Status.NS,
    )
    return Prediction.objects.create(
        fixture=fixture,
        lambda_home=1.5,
        lambda_away=1.2,
        lambda_total=2.7,
        p_over_15=0.9,
        p_over_25=0.72,
        p_over_35=0.4,
        p_btts=0.55,
        features_json={"signals": _signals(o25=True)},
    )


@pytest.mark.django_db
def test_todays_picks_ok(client, sample_prediction):
    response = client.get(reverse("picks"))
    assert response.status_code == 200
    assert b"Today" in response.content
    assert b"Home" in response.content
    assert b"Pending" in response.content
    # Unfinished: no live score even if goals were set.
    sample_prediction.fixture.goals_home = 1
    sample_prediction.fixture.goals_away = 0
    sample_prediction.fixture.status = Fixture.Status.LIVE
    sample_prediction.fixture.save()
    response = client.get(reverse("picks"))
    assert b"Pending" in response.content
    assert b"1:0" not in response.content


def test_today_picks_start_uses_launch(settings) -> None:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    msk = ZoneInfo("Europe/Moscow")
    settings.SITE_LAUNCH_AT = "2026-10-24T18:00:00"
    start = datetime(2026, 10, 24, 7, 30, tzinfo=msk)
    end = datetime(2026, 10, 25, 7, 30, tzinfo=msk)
    assert today_picks_start(start, end) == site_launch_at()
    # After launch batch — full window.
    later_start = datetime(2026, 10, 25, 7, 30, tzinfo=msk)
    later_end = datetime(2026, 10, 26, 7, 30, tzinfo=msk)
    assert today_picks_start(later_start, later_end) == later_start


@pytest.mark.django_db
def test_tomorrows_picks_ok(client, db):
    league = League.objects.create(
        api_id=39,
        name="PL",
        country="England",
        season=2026,
        is_active=True,
    )
    home = Team.objects.create(api_id=1, name="HomeT")
    away = Team.objects.create(api_id=2, name="AwayT")
    start, end = tomorrow_batch_window()
    kick = start + timedelta(hours=3)
    fx = Fixture.objects.create(
        api_id=5002,
        league=league,
        season=2026,
        home=home,
        away=away,
        kickoff_at=kick,
        status=Fixture.Status.NS,
    )
    Prediction.objects.create(
        fixture=fx,
        lambda_home=1.5,
        lambda_away=1.2,
        lambda_total=2.7,
        p_over_15=0.9,
        p_over_25=0.7,
        p_over_35=0.4,
        p_btts=0.55,
        features_json={"signals": _signals(o25=True)},
    )
    response = client.get(reverse("picks_tomorrow"))
    assert response.status_code == 200
    assert b"Tomorrow" in response.content
    assert b"HomeT" in response.content
    assert b"O2.5" in response.content
    # Tomorrow: no accuracy cards / score column.
    assert b"Picks Accuracy" not in response.content
    assert b">Score<" not in response.content
    assert b"Pending" not in response.content


@pytest.mark.django_db
def test_live_match_excluded_from_kpi(db):
    from apps.dashboard.views import _pick_accuracy_kpi

    league = League.objects.create(
        api_id=39,
        name="PL",
        country="England",
        season=2026,
        is_active=True,
    )
    home = Team.objects.create(api_id=10, name="H")
    away = Team.objects.create(api_id=11, name="A")
    fx = Fixture.objects.create(
        api_id=7002,
        league=league,
        season=2026,
        home=home,
        away=away,
        kickoff_at=timezone.now(),
        status=Fixture.Status.LIVE,
        goals_home=0,
        goals_away=0,
    )
    Prediction.objects.create(
        fixture=fx,
        lambda_home=1.5,
        lambda_away=1.2,
        lambda_total=2.7,
        p_over_15=0.9,
        p_over_25=0.7,
        p_over_35=0.4,
        features_json={"signals": _signals(o25=True)},
    )
    kpi = _pick_accuracy_kpi(
        Prediction.objects.select_related("fixture"),
    )
    assert kpi["o25"]["picked"] == 0
    assert kpi["count"] == 0


@pytest.mark.django_db
def test_btts_only_signal_excluded_from_picks(client, db):
    """Legacy BTTS-only rows are not listed after product drop."""
    league = League.objects.create(
        api_id=39,
        name="PL",
        country="England",
        season=2026,
        is_active=True,
    )
    home = Team.objects.create(api_id=20, name="BttsOnly")
    away = Team.objects.create(api_id=21, name="AwayX")
    start, end = current_batch_window()
    list_start = today_picks_start(start, end)
    kick = list_start + timedelta(hours=2)
    if kick <= timezone.now():
        kick = timezone.now() + timedelta(hours=1)
    fx = Fixture.objects.create(
        api_id=8001,
        league=league,
        season=2026,
        home=home,
        away=away,
        kickoff_at=kick,
        status=Fixture.Status.NS,
    )
    Prediction.objects.create(
        fixture=fx,
        lambda_home=1.6,
        lambda_away=1.4,
        lambda_total=3.0,
        p_over_15=0.92,
        p_over_25=0.55,
        p_over_35=0.30,
        p_btts=0.70,
        features_json={
            "signals": {
                "o15": False,
                "o25": False,
                "o35": False,
                "btts": True,
                "primary": "btts",
            },
        },
    )
    response = client.get(reverse("picks"))
    assert response.status_code == 200
    assert b"BttsOnly" not in response.content
    assert b"BTTS" not in response.content


def test_min_odds_filter() -> None:
    from apps.dashboard.templatetags.dashboard_extras import (
        min_odds,
    )

    assert min_odds(0.5) == "2.00"
    assert min_odds(0.72) == "1.39"
    assert min_odds(None) == "—"


@pytest.mark.django_db
def test_match_detail_ok(client, sample_prediction):
    fid = sample_prediction.fixture_id
    response = client.get(
        reverse("match_detail", args=[fid]),
    )
    assert response.status_code == 200
    body = response.content.decode()
    assert "2.5" in body
    assert "Home" in body
    assert "min odds" in body
    assert "Context" not in body
    # Main list should not dump raw model % on picks page.
    picks = client.get(reverse("picks"))
    assert b"72%" not in picks.content


@pytest.mark.django_db
def test_history_empty_ok(client):
    response = client.get(reverse("history"))
    assert response.status_code == 200
    assert b"No dates yet" in response.content
    assert b"Yesterday" not in response.content


@pytest.mark.django_db
def test_history_pick_accuracy(client, db):
    from apps.core.stats_window import stats_since
    from apps.dashboard.views import _pick_accuracy_kpi

    league = League.objects.create(
        api_id=39,
        name="PL",
        country="England",
        season=2026,
        is_active=True,
    )
    home = Team.objects.create(api_id=10, name="H")
    away = Team.objects.create(api_id=11, name="A")
    kick = stats_since() + timedelta(hours=1)
    fx = Fixture.objects.create(
        api_id=7001,
        league=league,
        season=2026,
        home=home,
        away=away,
        kickoff_at=kick,
        status=Fixture.Status.FT,
        goals_home=2,
        goals_away=1,
    )
    Prediction.objects.create(
        fixture=fx,
        lambda_home=1.5,
        lambda_away=1.2,
        lambda_total=2.7,
        p_over_15=0.9,
        p_over_25=0.7,
        p_over_35=0.4,
        p_btts=0.55,
        features_json={"signals": _signals(o25=True)},
    )
    kpi = _pick_accuracy_kpi(
        Prediction.objects.select_related("fixture"),
    )
    assert kpi["o25"]["picked"] == 1
    assert kpi["o25"]["wins"] == 1
    assert kpi["count"] == 1

    local = timezone.localtime(kick)
    day = local.strftime("%Y-%m-%d")
    response = client.get(reverse("history") + f"?date={day}")
    assert response.status_code == 200
    assert b"1 won / 1 picked" in response.content
    assert b"Yesterday" not in response.content
    assert b"Over 3.5" not in response.content
    assert local.strftime("%d.%m.%Y").encode() in response.content
    # Default (no date) picks latest day with stats.
    default = client.get(reverse("history"))
    assert default.status_code == 200
    assert local.strftime("%d.%m.%Y").encode() in default.content


@pytest.mark.django_db
def test_health_ok(client):
    response = client.get(reverse("health"))
    assert response.status_code == 200
    assert response.content == b"ok"
