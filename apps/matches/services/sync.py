"""Upsert teams and fixtures from API-Football."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from django.db import transaction
from django.db.models import Exists, OuterRef, Q, QuerySet
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.leagues.models import League, Team
from apps.matches.models import Fixture
from apps.matches.services.api_football import (
    ApiFootballClient,
    ApiFootballError,
    RateLimitError,
)
from apps.matches.services.status import map_status

logger = logging.getLogger(__name__)

# Keep year-1 seasons (e.g. 2025/26 EU) in the daily schedule sync.
CURRENT_SEASON_LOOKBACK_YEARS = 1


@dataclass
class SyncStats:
    """Counters for one sync run."""

    leagues: int = 0
    skipped: int = 0
    fixtures_seen: int = 0
    fixtures_created: int = 0
    fixtures_updated: int = 0
    teams_created: int = 0
    teams_updated: int = 0
    api_requests: int = 0
    stopped_reason: str = ""
    errors: list[str] = field(default_factory=list)


def sync_active_leagues(
    client: ApiFootballClient | None = None,
    *,
    max_requests: int | None = None,
    skip_synced: bool = True,
    only_unsynced: bool = False,
) -> SyncStats:
    """Sync fixtures for active leagues (resume-friendly)."""
    client = client or ApiFootballClient()
    stats = SyncStats()
    leagues = _league_queryset(
        skip_synced=skip_synced,
        only_unsynced=only_unsynced,
    )
    for league in leagues:
        if max_requests is not None and client.request_count >= max_requests:
            stats.stopped_reason = f"max_requests={max_requests}"
            break
        if skip_synced and league.last_synced_at:
            stats.skipped += 1
            continue
        try:
            league_stats = sync_league(league, client)
        except RateLimitError as exc:
            msg = f"{league}: {exc}"
            logger.error("%s", msg)
            stats.errors.append(msg)
            stats.stopped_reason = "rate_limit"
            break
        except ApiFootballError as exc:
            msg = f"{league}: {exc}"
            logger.error("Sync failed for %s: %s", league, exc)
            stats.errors.append(msg)
            if _is_auth_error(exc):
                stats.stopped_reason = "auth"
                break
            if _is_plan_season_error(exc):
                # Do not retry seasons unavailable on this plan.
                league.last_synced_at = timezone.now()
                league.is_active = False
                league.save(
                    update_fields=[
                        "last_synced_at",
                        "is_active",
                        "updated_at",
                    ],
                )
                stats.skipped += 1
            continue
        except Exception as exc:
            msg = f"{league}: {exc}"
            logger.exception("Sync failed for %s", league)
            stats.errors.append(msg)
            continue
        stats.leagues += 1
        stats.fixtures_seen += league_stats.fixtures_seen
        stats.fixtures_created += league_stats.fixtures_created
        stats.fixtures_updated += league_stats.fixtures_updated
        stats.teams_created += league_stats.teams_created
        stats.teams_updated += league_stats.teams_updated
    stats.api_requests = client.request_count
    return stats


def _league_queryset(
    *,
    skip_synced: bool,
    only_unsynced: bool,
) -> QuerySet[League]:
    qs = League.objects.filter(is_active=True).order_by(
        "country",
        "name",
        "season",
    )
    if only_unsynced or skip_synced:
        # Prefer unsynced first when resuming.
        qs = qs.order_by(
            "last_synced_at",
            "country",
            "name",
            "season",
        )
    return qs


def current_season_leagues() -> QuerySet[League]:
    """Active leagues for current (+ lookback) seasons.

    Includes seasons that still have upcoming fixtures even
    if the year label is older (calendar vs EU seasons).
    """
    today = timezone.localdate()
    min_year = today.year - CURRENT_SEASON_LOOKBACK_YEARS
    upcoming = Fixture.objects.filter(
        league_id=OuterRef("pk"),
        status__in=(
            Fixture.Status.NS,
            Fixture.Status.TBD,
        ),
        kickoff_at__gte=timezone.now() - timedelta(days=1),
    )
    return (
        League.objects.filter(is_active=True)
        .filter(
            Exists(upcoming) | Q(season__gte=min_year),
        )
        .order_by("country", "name", "season")
    )


def sync_schedule(
    client: ApiFootballClient | None = None,
    *,
    max_requests: int | None = None,
) -> SyncStats:
    """Daily: full fixture list for current-season leagues."""
    client = client or ApiFootballClient()
    stats = SyncStats()
    for league in current_season_leagues():
        if max_requests is not None and client.request_count >= max_requests:
            stats.stopped_reason = f"max_requests={max_requests}"
            break
        try:
            league_stats = sync_league(league, client)
        except RateLimitError as exc:
            msg = f"{league}: {exc}"
            logger.error("%s", msg)
            stats.errors.append(msg)
            stats.stopped_reason = "rate_limit"
            break
        except ApiFootballError as exc:
            msg = f"{league}: {exc}"
            logger.error("Schedule sync failed %s", league)
            stats.errors.append(msg)
            if _is_auth_error(exc):
                stats.stopped_reason = "auth"
                break
            if _is_plan_season_error(exc):
                league.is_active = False
                league.save(
                    update_fields=["is_active", "updated_at"],
                )
                stats.skipped += 1
            continue
        except Exception as exc:
            msg = f"{league}: {exc}"
            logger.exception("Schedule sync failed %s", league)
            stats.errors.append(msg)
            continue
        stats.leagues += 1
        stats.fixtures_seen += league_stats.fixtures_seen
        stats.fixtures_created += league_stats.fixtures_created
        stats.fixtures_updated += league_stats.fixtures_updated
        stats.teams_created += league_stats.teams_created
        stats.teams_updated += league_stats.teams_updated
    stats.api_requests = client.request_count
    return stats


def sync_results(
    client: ApiFootballClient | None = None,
    *,
    days_back: int = 1,
    tz_name: str = "Europe/Moscow",
) -> SyncStats:
    """Hourly: upsert fixtures for today and recent days.

    Uses fixtures?date=… (1 request per calendar day).
    Only leagues already in DB are updated; others skipped.
    """
    client = client or ApiFootballClient()
    stats = SyncStats()
    today = timezone.localdate()
    dates = [
        today - timedelta(days=offset) for offset in range(days_back, -1, -1)
    ]
    for day in dates:
        day_s = day.isoformat()
        try:
            raw_list = client.get_fixtures_by_date(
                day_s,
                tz=tz_name,
            )
        except RateLimitError as exc:
            stats.errors.append(str(exc))
            stats.stopped_reason = "rate_limit"
            break
        except ApiFootballError as exc:
            stats.errors.append(f"{day_s}: {exc}")
            continue
        for item in raw_list:
            try:
                created, team_delta, skipped = _upsert_fixture_from_item(item)
            except Exception as exc:
                fid = _safe_fixture_id(item)
                msg = f"fixture {fid}: {exc}"
                logger.warning("Skip %s", msg)
                stats.errors.append(msg)
                continue
            if skipped:
                stats.skipped += 1
                continue
            stats.fixtures_seen += 1
            if created:
                stats.fixtures_created += 1
            else:
                stats.fixtures_updated += 1
            stats.teams_created += team_delta[0]
            stats.teams_updated += team_delta[1]
    stats.api_requests = client.request_count
    return stats


def _upsert_fixture_from_item(
    item: dict[str, Any],
) -> tuple[bool, tuple[int, int], bool]:
    """Resolve league from payload; skip unknown leagues."""
    league_data = item.get("league") or {}
    league_api_id = league_data.get("id")
    season = league_data.get("season")
    if not league_api_id or season is None:
        raise ValueError("missing league.id/season")
    league = League.objects.filter(
        api_id=int(league_api_id),
        season=int(season),
    ).first()
    if league is None:
        return False, (0, 0), True
    created, team_delta = _upsert_fixture(league, item)
    return created, team_delta, False


def _is_auth_error(exc: Exception) -> bool:
    """True if the API rejected the application key."""
    text = str(exc).lower()
    return "token" in text or "application key" in text


def _is_plan_season_error(exc: Exception) -> bool:
    """True if season is outside the subscription window."""
    text = str(exc).lower()
    return "plan" in text and "season" in text


def sync_league(
    league: League,
    client: ApiFootballClient,
) -> SyncStats:
    """Sync one league season from the API."""
    stats = SyncStats(leagues=1)
    raw_list = client.get_fixtures(
        league_id=league.api_id,
        season=league.season,
    )
    for item in raw_list:
        try:
            created_fx, team_delta = _upsert_fixture(
                league,
                item,
            )
        except Exception as exc:
            fid = _safe_fixture_id(item)
            msg = f"fixture {fid}: {exc}"
            logger.warning("Skip %s", msg)
            stats.errors.append(msg)
            continue
        stats.fixtures_seen += 1
        if created_fx:
            stats.fixtures_created += 1
        else:
            stats.fixtures_updated += 1
        stats.teams_created += team_delta[0]
        stats.teams_updated += team_delta[1]
    league.last_synced_at = timezone.now()
    league.save(update_fields=["last_synced_at", "updated_at"])
    return stats


def _upsert_fixture(
    league: League,
    item: dict[str, Any],
) -> tuple[bool, tuple[int, int]]:
    """Create or update one fixture. Return flags."""
    fixture_data = item.get("fixture") or {}
    teams_data = item.get("teams") or {}
    goals_data = item.get("goals") or {}
    league_data = item.get("league") or {}

    api_id = fixture_data.get("id")
    if not api_id:
        raise ValueError("missing fixture.id")

    home_raw = teams_data.get("home") or {}
    away_raw = teams_data.get("away") or {}
    home, h_created, h_updated = _upsert_team(home_raw)
    away, a_created, a_updated = _upsert_team(away_raw)
    teams_created = h_created + a_created
    teams_updated = h_updated + a_updated

    kickoff = _parse_kickoff(fixture_data.get("date"))
    status_short = (fixture_data.get("status") or {}).get(
        "short",
    )
    status = map_status(status_short)
    round_name = league_data.get("round") or ""
    season = league_data.get("season") or league.season

    goals_home = goals_data.get("home")
    goals_away = goals_data.get("away")

    defaults = {
        "league": league,
        "season": int(season),
        "round": str(round_name)[:64],
        "home": home,
        "away": away,
        "kickoff_at": kickoff,
        "status": status,
        "goals_home": goals_home,
        "goals_away": goals_away,
    }

    with transaction.atomic():
        _obj, created = Fixture.objects.update_or_create(
            api_id=int(api_id),
            defaults=defaults,
        )
    return created, (teams_created, teams_updated)


def _upsert_team(
    raw: dict[str, Any],
) -> tuple[Team, int, int]:
    """Upsert a team from API payload fragment."""
    api_id = raw.get("id")
    name = (raw.get("name") or "").strip()
    if not api_id or not name:
        raise ValueError("missing team id/name")
    logo = raw.get("logo") or ""
    defaults = {
        "name": name[:128],
        "logo_url": logo[:200] if logo else "",
    }
    team, created = Team.objects.update_or_create(
        api_id=int(api_id),
        defaults=defaults,
    )
    if created:
        return team, 1, 0
    return team, 0, 1


def _parse_kickoff(value: str | None) -> datetime:
    """Parse ISO kickoff into aware datetime."""
    if not value:
        raise ValueError("missing fixture.date")
    parsed = parse_datetime(value)
    if parsed is None:
        raise ValueError(f"bad fixture.date: {value!r}")
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(
            parsed,
            timezone.get_current_timezone(),
        )
    return parsed


def _safe_fixture_id(item: dict[str, Any]) -> Any:
    try:
        return (item.get("fixture") or {}).get("id")
    except AttributeError:
        return "?"
