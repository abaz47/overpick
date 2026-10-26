"""Daily Pick batch window (00:00 Europe/Moscow calendar day)."""

from __future__ import annotations

from datetime import datetime, timedelta

from django.utils import timezone

BATCH_HOUR = 0
BATCH_MINUTE = 0


def _cutover(local: datetime) -> datetime:
    return local.replace(
        hour=BATCH_HOUR,
        minute=BATCH_MINUTE,
        second=0,
        microsecond=0,
    )


def current_batch_window(
    now: datetime | None = None,
) -> tuple[datetime, datetime]:
    """Return [batch_start, batch_end) for Today's Picks.

    Cutover is 00:00 MSK (calendar day). Tips for a calendar
    day are locked the evening before (cron 20:00) and are
    not rewritten when the next evening job runs.
    """
    local = timezone.localtime(now or timezone.now())
    today_cut = _cutover(local)
    start = today_cut if local >= today_cut else today_cut - timedelta(days=1)
    end = start + timedelta(days=1)
    return start, end


def tomorrow_batch_window(
    now: datetime | None = None,
) -> tuple[datetime, datetime]:
    """Next calendar-day slice after the current batch."""
    start, end = current_batch_window(now)
    return end, end + timedelta(days=1)


def batch_window_for(
    which: str = "today",
    *,
    now: datetime | None = None,
) -> tuple[datetime, datetime]:
    """today → current calendar day; tomorrow → next day."""
    if which == "tomorrow":
        return tomorrow_batch_window(now)
    return current_batch_window(now)


def batch_containing(
    kickoff: datetime,
) -> tuple[datetime, datetime]:
    """Batch window that contains a kickoff (MSK midnight)."""
    local = timezone.localtime(kickoff)
    cut = _cutover(local)
    start = cut if local >= cut else cut - timedelta(days=1)
    return start, start + timedelta(days=1)


def batch_label(start: datetime) -> str:
    """Short MSK label for UI, e.g. 25.10 00:00."""
    local = timezone.localtime(start)
    return local.strftime("%d.%m %H:%M")
