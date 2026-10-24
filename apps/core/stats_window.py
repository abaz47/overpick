"""Shared launch / History cutoff helpers (MSK)."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime

MSK = ZoneInfo("Europe/Moscow")


def _parse_msk(
    raw: str,
    fallback: datetime,
) -> datetime:
    parsed = parse_datetime(raw)
    if parsed is None:
        parsed = fallback
    if timezone.is_naive(parsed):
        parsed = parsed.replace(tzinfo=MSK)
    return parsed


def site_launch_at() -> datetime:
    """Soft launch: Today's picks/KPI from this MSK time."""
    raw = str(
        getattr(
            settings,
            "SITE_LAUNCH_AT",
            "2026-10-24T18:00:00",
        ),
    )
    return _parse_msk(
        raw,
        datetime(2026, 10, 24, 18, 0, 0),
    )


def stats_since() -> datetime:
    """Earliest kickoff counted in History KPIs.

    History storage starts the day after soft launch.
    """
    raw = str(
        getattr(
            settings,
            "STATS_SINCE",
            "2026-10-25T00:00:00",
        ),
    )
    return _parse_msk(
        raw,
        datetime(2026, 10, 25, 0, 0, 0),
    )


def today_picks_start(
    batch_start: datetime,
    batch_end: datetime,
) -> datetime:
    """Kickoff floor for Today's list during the launch batch."""
    launch = site_launch_at()
    if batch_start <= launch < batch_end:
        return launch
    return batch_start
