from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from bot.scheduler import next_pick_time
from bot.db import connect
from bot.storage import Storage

MSK = ZoneInfo("Europe/Moscow")


def test_next_pick_time_same_day():
    now = datetime(2026, 11, 10, 9, 0, tzinfo=MSK)
    assert next_pick_time(now, "12:00", "Europe/Moscow") == datetime(2026, 11, 10, 12, 0, tzinfo=MSK)


def test_next_pick_time_next_day_when_passed():
    now = datetime(2026, 11, 10, 13, 0, tzinfo=MSK)
    assert next_pick_time(now, "12:00", "Europe/Moscow") == datetime(2026, 11, 11, 12, 0, tzinfo=MSK)


def test_next_pick_time_equal_is_next_day():
    now = datetime(2026, 11, 10, 12, 0, tzinfo=MSK)
    assert next_pick_time(now, "12:00", "Europe/Moscow") == datetime(2026, 11, 11, 12, 0, tzinfo=MSK)


def test_next_pick_time_another_tz():
    utc = timezone.utc
    now = datetime(2026, 11, 10, 8, 30, tzinfo=utc)  # 11:30 МСК
    result = next_pick_time(now, "12:00", "Europe/Moscow")
    assert result.astimezone(MSK) == datetime(2026, 11, 10, 12, 0, tzinfo=MSK)
