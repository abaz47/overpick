"""Daily batch cutover at 00:00 MSK (calendar day)."""

from datetime import datetime
from zoneinfo import ZoneInfo

from apps.predictions.services.batch import (
    batch_containing,
    current_batch_window,
    tomorrow_batch_window,
)

MSK = ZoneInfo("Europe/Moscow")


def test_before_midnight_is_previous_calendar_day() -> None:
    now = datetime(2026, 10, 26, 10, 0, tzinfo=MSK)
    start, end = current_batch_window(now)
    assert start == datetime(2026, 10, 26, 0, 0, tzinfo=MSK)
    assert end == datetime(2026, 10, 27, 0, 0, tzinfo=MSK)
    nxt_s, nxt_e = tomorrow_batch_window(now)
    assert nxt_s == end
    assert nxt_e == datetime(2026, 10, 28, 0, 0, tzinfo=MSK)


def test_evening_still_same_calendar_today() -> None:
    """20:00 job locks tomorrow; UI Today stays calendar day."""
    now = datetime(2026, 10, 26, 20, 30, tzinfo=MSK)
    start, end = current_batch_window(now)
    assert start == datetime(2026, 10, 26, 0, 0, tzinfo=MSK)
    assert end == datetime(2026, 10, 27, 0, 0, tzinfo=MSK)
    nxt_s, nxt_e = tomorrow_batch_window(now)
    assert nxt_s == datetime(2026, 10, 27, 0, 0, tzinfo=MSK)
    assert nxt_e == datetime(2026, 10, 28, 0, 0, tzinfo=MSK)


def test_batch_containing_morning_match() -> None:
    kick = datetime(2026, 10, 26, 15, 0, tzinfo=MSK)
    start, end = batch_containing(kick)
    assert start == datetime(2026, 10, 26, 0, 0, tzinfo=MSK)
    assert end == datetime(2026, 10, 27, 0, 0, tzinfo=MSK)
