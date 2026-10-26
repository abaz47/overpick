"""Daily batch cutover at 20:00 MSK."""

from datetime import datetime
from zoneinfo import ZoneInfo

from apps.predictions.services.batch import (
    batch_containing,
    current_batch_window,
    tomorrow_batch_window,
)

MSK = ZoneInfo("Europe/Moscow")


def test_before_cutover_uses_yesterday_20() -> None:
    now = datetime(2026, 10, 26, 10, 0, tzinfo=MSK)
    start, end = current_batch_window(now)
    assert start == datetime(2026, 10, 25, 20, 0, tzinfo=MSK)
    assert end == datetime(2026, 10, 26, 20, 0, tzinfo=MSK)
    nxt_s, nxt_e = tomorrow_batch_window(now)
    assert nxt_s == end
    assert nxt_e == datetime(2026, 10, 27, 20, 0, tzinfo=MSK)


def test_at_cutover_rolls_forward() -> None:
    now = datetime(2026, 10, 26, 20, 0, tzinfo=MSK)
    start, end = current_batch_window(now)
    assert start == datetime(2026, 10, 26, 20, 0, tzinfo=MSK)
    assert end == datetime(2026, 10, 27, 20, 0, tzinfo=MSK)


def test_batch_containing_evening_match() -> None:
    kick = datetime(2026, 10, 26, 21, 0, tzinfo=MSK)
    start, end = batch_containing(kick)
    assert start == datetime(2026, 10, 26, 20, 0, tzinfo=MSK)
    assert end == datetime(2026, 10, 27, 20, 0, tzinfo=MSK)
