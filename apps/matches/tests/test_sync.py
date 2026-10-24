"""Tests for fixture sync (mocked API)."""

from __future__ import annotations

import pytest
from django.utils import timezone

from apps.leagues.models import League, Team
from apps.matches.models import Fixture
from apps.matches.services.sync import sync_league


class FakeClient:
    """Minimal stand-in for ApiFootballClient."""

    def __init__(self, payload: list) -> None:
        self.payload = payload
        self.calls: list[tuple[int, int]] = []

    def get_fixtures(
        self,
        league_id: int,
        season: int,
    ) -> list:
        self.calls.append((league_id, season))
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
