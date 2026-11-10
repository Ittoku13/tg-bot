from datetime import datetime, timedelta, timezone

import pytest

from bot.db import connect
from bot.storage import Settings, Storage

MSK = timezone(timedelta(hours=3))
NOW = datetime.now(MSK)


@pytest.fixture()
def storage(tmp_path):
    conn = connect(tmp_path / "test.db")
    yield Storage(conn)
    conn.close()


def test_settings_defaults(storage):
    s = storage.settings(-1)
    assert s == Settings(chat_id=-1)


def test_update_settings_roundtrip(storage):
    s = storage.update_settings(-1, role_name="Пчела", pick_time="09:30", character="adult")
    assert s.role_name == "Пчела"
    assert s.pick_time == "09:30"
    assert s.character == "adult"
    assert storage.settings(-1).role_name == "Пчела"


@pytest.mark.parametrize("bad", [
    {"character": "evil"},
    {"mock_mode": "everyone"},
    {"mock_chance": 101},
    {"mock_chance": -1},
    {"mock_cooldown_min": -5},
    {"pick_time": "25:00"},
    {"pick_time": "noon"},
])
def test_update_settings_validation(storage, bad):
    with pytest.raises(ValueError):
        storage.update_settings(-1, **bad)


def test_users_upsert_and_list(storage):
    storage.upsert_user(-1, 10, "oleg", "Олег", NOW)
    storage.upsert_user(-1, 10, "oleg2", "Олег", NOW + timedelta(hours=1))
    storage.upsert_user(-1, 20, None, "Пчела", NOW)
    users = storage.list_users(-1)
    assert [(u.user_id, u.username, u.first_name) for u in users] == [
        (10, "oleg2", "Олег"),
        (20, None, "Пчела"),
    ]


def test_display_name_fallback(storage):
    storage.upsert_user(-1, 30, None, None, NOW)
    assert storage.list_users(-1)[0].display_name == "user_30"
    storage.upsert_user(-1, 31, "bee", None, NOW)
    assert storage.list_users(-1)[1].display_name == "@bee"


def test_picks_top_periods_and_clear(storage):
    day = timedelta(days=1)
    for i in range(3):
        storage.add_pick(-1, 10, NOW - i * day)
    storage.add_pick(-1, 20, NOW - 40 * day)
    assert storage.top(-1, None) == [(10, 3), (20, 1)]
    assert storage.top(-1, 30) == [(10, 3)]
    assert storage.top(-1, 7) == [(10, 3)]
    assert storage.count_for(-1, 20, None) == 1
    assert storage.last_pick(-1) == (10, NOW)
    assert storage.last_pick_for(-1, 20) == NOW - 40 * day
    assert storage.last_pick_for(-1, 99) is None
    storage.clear_picks(-1)
    assert storage.top(-1, None) == []
    assert storage.last_pick(-1) is None


def test_settings_get_or_create(storage):
    assert storage.settings(-1) == Settings(chat_id=-1)
    assert storage.chat_ids_with_auto_pick() == [-1]


def test_top_tie_break_by_earliest_last_pick(storage):
    storage.add_pick(-1, 10, NOW - 5 * timedelta(days=1))
    storage.add_pick(-1, 10, NOW - timedelta(days=1))
    storage.add_pick(-1, 20, NOW - 3 * timedelta(days=1))
    storage.add_pick(-1, 20, NOW - 2 * timedelta(days=1))
    assert storage.top(-1, None) == [(20, 2), (10, 2)]


def test_mock_targets_and_last_mock(storage):
    storage.replace_mock_targets(-1, [1, 2, 2])
    assert storage.mock_targets(-1) == {1, 2}
    storage.replace_mock_targets(-1, [3])
    assert storage.mock_targets(-1) == {3}
    assert storage.last_mock_at(-1) is None
    storage.set_last_mock(-1, NOW)
    assert storage.last_mock_at(-1) == NOW


def test_chat_ids_with_auto_pick(storage):
    storage.settings(-1)
    storage.settings(-2)
    storage.update_settings(-2, auto_pick_enabled=False)
    assert storage.chat_ids_with_auto_pick() == [-1]
