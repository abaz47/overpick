"""Tests for fixture sync (mocked API)."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.leagues.models import League, Team
from apps.matches.models import Fixture
from apps.matches.services.sync import (
    current_season_leagues,
    sync_league,
    sync_results,
)


class FakeClient:
    """Minimal stand-in for ApiFootballClient."""

    def __init__(self, payload: list) -> None:
        self.payload = payload
        self.calls: list[tuple[int, int]] = []
        self.date_calls: list[str] = []
        self.request_count = 0

    def get_fixtures(
        self,
        league_id: int,
        season: int,
    ) -> list:
        self.calls.append((league_id, season))
        self.request_count += 1
        return self.payload

    def get_fixtures_by_date(
        self,
        date: str,
        *,
        tz: str = "Europe/Moscow",
    ) -> list:
        self.date_calls.append(date)
        self.request_count += 1
        return self.payload


@pytest.mark.django_db
def test_sync_league_creates_fixture() -> None:
    league = League.objects.create(
        api_id=39,
        name="Premier League",
        country="England",
        code="PL",
        season=2026,
    )
    payload = [
        {
            "fixture": {
                "id": 999001,
                "date": "2026-10-25T14:00:00+00:00",
                "status": {"short": "NS"},
            },
            "league": {
                "season": 2026,
                "round": "Regular Season - 9",
            },
            "teams": {
                "home": {
                    "id": 33,
                    "name": "Manchester United",
                    "logo": "https://example.com/33.png",
                },
                "away": {
                    "id": 40,
                    "name": "Liverpool",
                    "logo": "",
                },
            },
            "goals": {"home": None, "away": None},
        },
    ]
    client = FakeClient(payload)
    stats = sync_league(league, client)  # type: ignore[arg-type]

    assert client.calls == [(39, 2026)]
    assert stats.fixtures_created == 1
    assert stats.teams_created == 2
    fx = Fixture.objects.get(api_id=999001)
    assert fx.home.name == "Manchester United"
    assert fx.away.name == "Liverpool"
    assert fx.status == Fixture.Status.NS
    assert fx.goals_home is None
    assert timezone.is_aware(fx.kickoff_at)


@pytest.mark.django_db
def test_sync_league_updates_finished() -> None:
    league = League.objects.create(
        api_id=39,
        name="Premier League",
        country="England",
        code="PL",
        season=2026,
    )
    home = Team.objects.create(api_id=33, name="Home")
    away = Team.objects.create(api_id=40, name="Away")
    Fixture.objects.create(
        api_id=999002,
        league=league,
        season=2026,
        home=home,
        away=away,
        kickoff_at=timezone.now(),
        status=Fixture.Status.NS,
    )
    payload = [
        {
            "fixture": {
                "id": 999002,
                "date": "2026-10-20T14:00:00+00:00",
                "status": {"short": "FT"},
            },
            "league": {
                "season": 2026,
                "round": "Regular Season - 8",
            },
            "teams": {
                "home": {"id": 33, "name": "Home FC"},
                "away": {"id": 40, "name": "Away FC"},
            },
            "goals": {"home": 2, "away": 1},
        },
    ]
    stats = sync_league(
        league,
        FakeClient(payload),  # type: ignore[arg-type]
    )
    assert stats.fixtures_updated == 1
    fx = Fixture.objects.get(api_id=999002)
    assert fx.status == Fixture.Status.FT
    assert fx.goals_home == 2
    assert fx.goals_away == 1
    assert fx.total_goals == 3
    home.refresh_from_db()
    assert home.name == "Home FC"


@pytest.mark.django_db
def test_sync_results_updates_known_league() -> None:
    league = League.objects.create(
        api_id=39,
        name="Premier League",
        country="England",
        code="PL",
        season=2026,
        is_active=True,
    )
    home = Team.objects.create(api_id=33, name="Home")
    away = Team.objects.create(api_id=40, name="Away")
    Fixture.objects.create(
        api_id=999003,
        league=league,
        season=2026,
        home=home,
        away=away,
        kickoff_at=timezone.now() - timedelta(hours=2),
        status=Fixture.Status.NS,
    )
    payload = [
        {
            "fixture": {
                "id": 999003,
                "date": "2026-10-24T12:00:00+00:00",
                "status": {"short": "FT"},
            },
            "league": {
                "id": 39,
                "season": 2026,
                "round": "Regular Season - 9",
            },
            "teams": {
                "home": {"id": 33, "name": "Home"},
                "away": {"id": 40, "name": "Away"},
            },
            "goals": {"home": 3, "away": 1},
        },
        {
            # Unknown competition — skipped.
            "fixture": {
                "id": 888001,
                "date": "2026-10-24T12:00:00+00:00",
                "status": {"short": "FT"},
            },
            "league": {
                "id": 1,
                "season": 2026,
                "round": "Final",
            },
            "teams": {
                "home": {"id": 1, "name": "A"},
                "away": {"id": 2, "name": "B"},
            },
            "goals": {"home": 1, "away": 0},
        },
    ]
    stats = sync_results(
        FakeClient(payload),  # type: ignore[arg-type]
        days_back=0,
    )
    assert stats.fixtures_updated == 1
    assert stats.skipped == 1
    assert stats.api_requests == 1
    fx = Fixture.objects.get(api_id=999003)
    assert fx.status == Fixture.Status.FT
    assert fx.goals_home == 3
    assert not Fixture.objects.filter(api_id=888001).exists()


@pytest.mark.django_db
def test_current_season_leagues_includes_lookback() -> None:
    year = timezone.localdate().year
    League.objects.create(
        api_id=39,
        name="PL",
        country="England",
        season=year,
        is_active=True,
    )
    League.objects.create(
        api_id=40,
        name="Old",
        country="England",
        season=year - 3,
        is_active=True,
    )
    ids = set(
        current_season_leagues().values_list(
            "api_id",
            flat=True,
        ),
    )
    assert 39 in ids
    assert 40 not in ids
