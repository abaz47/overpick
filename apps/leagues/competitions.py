"""Competition helpers (domestic vs UEFA cups)."""

from __future__ import annotations

# API-Football ids for European club competitions.
UEFA_CUP_API_IDS: frozenset[int] = frozenset(
    {
        2,  # UEFA Champions League
        3,  # UEFA Europa League
        848,  # UEFA Europa Conference League
    },
)


def is_uefa_cup(league_api_id: int | None) -> bool:
    """True for UCL / UEL / UECL (form uses all team matches)."""
    if league_api_id is None:
        return False
    return int(league_api_id) in UEFA_CUP_API_IDS


def form_league_scope(
    league_id: int | None,
    league_api_id: int | None,
) -> int | None:
    """ORM league pk for venue form, or None = all competitions.

    UEFA cups mix clubs from many domestic leagues; last-N inside
    the cup alone is too sparse early in the group stage, so form
    is taken across all finished matches while μ stays cup-level.
    """
    if is_uefa_cup(league_api_id):
        return None
    return league_id
