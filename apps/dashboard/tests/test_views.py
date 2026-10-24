"""Smoke tests for dashboard pages."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.leagues.models import League, Team
from apps.matches.models import Fixture
from apps.predictions.models import Prediction


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
    fixture = Fixture.objects.create(
        api_id=5001,
        league=league,
        season=2026,
        home=home,
        away=away,
        kickoff_at=timezone.now() + timedelta(days=1),
        status=Fixture.Status.NS,
    )
    return Prediction.objects.create(
        fixture=fixture,
        lambda_home=1.5,
        lambda_away=1.2,
        lambda_total=2.7,
        p_over_15=0.8,
        p_over_25=0.55,
        p_over_35=0.3,
        features_json={
            "signals": {
                "o15": True,
                "o25": False,
                "o35": False,
            },
            "hs": 1.5,
            "hc": 1.0,
            "as": 1.2,
            "ac": 1.1,
            "home_last": {
                "scored": 1.6,
                "conceded": 1.0,
                "sample_size": 5,
            },
            "away_last": {
                "scored": 1.1,
                "conceded": 1.2,
                "sample_size": 5,
            },
            "league_mu_home_scored": 1.4,
            "league_mu_away_scored": 1.2,
            "n": 5,
            "min_n": 3,
            "shrink_k": 3,
            "last_weight": 0.6,
        },
    )


@pytest.mark.django_db
def test_upcoming_ok(client, sample_prediction):
    response = client.get(reverse("upcoming"))
    assert response.status_code == 200
    assert b"Home" in response.content
    assert b"Away" in response.content


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


@pytest.mark.django_db
def test_history_empty_ok(client):
    response = client.get(reverse("history"))
    assert response.status_code == 200


@pytest.mark.django_db
def test_upcoming_default_hours_window(client, sample_prediction):
    response = client.get(reverse("upcoming"))
    assert response.status_code == 200
    assert b"Next 48h" in response.content
    assert b"Kickoff (MSK)" in response.content
    assert b"Leagues" not in response.content


@pytest.mark.django_db
def test_health_ok(client):
    response = client.get(reverse("health"))
    assert response.status_code == 200
    assert response.content == b"ok"
