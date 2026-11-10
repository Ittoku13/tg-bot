from datetime import datetime, timedelta, timezone

import pytest

from bot.services.rating import PERIODS, format_top, period_keys
from bot.storage import UserRow

NOW = datetime(2026, 11, 10, tzinfo=timezone(timedelta(hours=3)))


def user(uid: int) -> UserRow:
    return UserRow(user_id=uid, username=None, first_name=f"User{uid}", last_active=NOW)


def test_periods_mapping():
    assert PERIODS == {"all": None, "month": 30, "week": 7}
    assert set(period_keys()) == {"all", "month", "week"}


def test_format_top():
    text = format_top([(user(1), 5), (user(2), 2)], "month", "Олег")
    assert "Топ по званию «Олег» за месяц:" in text
    assert "1. User1 — 5" in text
    assert "2. User2 — 2" in text


def test_format_top_unknown_period():
    with pytest.raises(KeyError):
        format_top([], "year", "Олег")
