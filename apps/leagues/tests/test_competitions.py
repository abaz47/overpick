"""Tests for UEFA vs domestic form scope."""

from apps.leagues.competitions import (
    UEFA_CUP_API_IDS,
    form_league_scope,
    is_uefa_cup,
)


def test_uefa_ids() -> None:
    assert 2 in UEFA_CUP_API_IDS
    assert 3 in UEFA_CUP_API_IDS
    assert 848 in UEFA_CUP_API_IDS
    assert is_uefa_cup(2) is True
    assert is_uefa_cup(39) is False


def test_form_league_scope_uefa_clears_filter() -> None:
    assert form_league_scope(99, 2) is None
    assert form_league_scope(99, 39) == 99
