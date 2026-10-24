"""Tests for seed_leagues command."""

import pytest
from django.core.management import call_command

from apps.leagues.defaults import DEFAULT_LEAGUES
from apps.leagues.models import League


@pytest.mark.django_db
def test_seed_leagues_creates_defaults() -> None:
    call_command("seed_leagues", "--season", "2026")
    assert League.objects.count() == len(DEFAULT_LEAGUES)
    pl = League.objects.get(api_id=39, season=2026)
    assert pl.is_active is True
    assert pl.code == "PL"


@pytest.mark.django_db
def test_seed_leagues_updates_existing_row() -> None:
    League.objects.create(
        api_id=39,
        name="Old",
        country="England",
        code="PL",
        season=2026,
        is_active=False,
    )
    call_command("seed_leagues", "--season", "2026")
    pl = League.objects.get(api_id=39, season=2026)
    assert pl.name == "Premier League"
    assert pl.is_active is True


@pytest.mark.django_db
def test_seed_leagues_season_range() -> None:
    call_command(
        "seed_leagues",
        "--from-season",
        "2022",
        "--to-season",
        "2023",
    )
    assert League.objects.filter(api_id=39).count() == 2
    assert League.objects.count() == len(DEFAULT_LEAGUES) * 2
