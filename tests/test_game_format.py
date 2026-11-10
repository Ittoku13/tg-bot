from datetime import datetime, timedelta, timezone

from bot.storage import UserRow

MSK = timezone(timedelta(hours=3))


def format_mystats(user: UserRow, role_name: str, count: int,
                   last: datetime | None) -> str:
    from bot.handlers.game import mystats_text
    return mystats_text(user, role_name, count, last)


def test_mystats_with_history():
    last = datetime(2026, 11, 1, 12, 0, tzinfo=MSK)
    text = format_mystats(UserRow(1, None, "Олег", last), "Олег", 3, last)
    assert "3" in text and "Олег" in text and "2026-11-01" in text


def test_mystats_zero():
    text = format_mystats(UserRow(1, None, "Олег", None), "Олег", 0, None)
    assert "0" in text
