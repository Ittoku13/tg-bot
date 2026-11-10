import random
from datetime import datetime, timedelta, timezone

from bot.services.picker import pick_candidate
from bot.storage import UserRow

NOW = datetime(2026, 11, 10, tzinfo=timezone(timedelta(hours=3)))


def make_users(*ids: int) -> list[UserRow]:
    return [UserRow(user_id=i, username=None, first_name=f"U{i}", last_active=NOW) for i in ids]


def test_picks_from_pool():
    rng = random.Random(1)
    users = make_users(1, 2, 3)
    assert pick_candidate(users, None, False, rng) in users


def test_excludes_last_when_possible():
    rng = random.Random(1)
    users = make_users(1, 2, 3)
    for _ in range(50):
        assert pick_candidate(users, 1, True, rng).user_id != 1


def test_single_user_pool_keeps_last():
    rng = random.Random(1)
    users = make_users(1)
    assert pick_candidate(users, 1, True, rng).user_id == 1


def test_empty_pool_returns_none():
    rng = random.Random(1)
    assert pick_candidate([], None, False, rng) is None
