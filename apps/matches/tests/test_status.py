"""Tests for API status mapping."""

from apps.matches.models import Fixture
from apps.matches.services.status import map_status


def test_map_direct_statuses() -> None:
    assert map_status("NS") == Fixture.Status.NS
    assert map_status("FT") == Fixture.Status.FT
    assert map_status("ht") == Fixture.Status.HT


def test_map_live_codes() -> None:
    assert map_status("1H") == Fixture.Status.LIVE
    assert map_status("2H") == Fixture.Status.LIVE
    assert map_status("ET") == Fixture.Status.LIVE


def test_map_unknown() -> None:
    assert map_status("XYZ") == Fixture.Status.OTHER
    assert map_status(None) == Fixture.Status.OTHER
