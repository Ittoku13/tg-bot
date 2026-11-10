import random
from datetime import datetime, timedelta, timezone

from bot.services.mockery import CONFUSABLES, corrupt_text, is_mockable, should_mock
from bot.storage import Settings

NOW = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)
TEXT = "Я эйчар и запрещаю удалёнку и гибрид для всех сотрудников компании"


def test_is_mockable_length():
    assert not is_mockable("коротко")
    assert is_mockable("Я эйчар и запрещаю удалёнку")


def test_corrupt_deterministic_with_seed():
    a = corrupt_text(TEXT, random.Random(42))
    b = corrupt_text(TEXT, random.Random(42))
    assert a == b and a != TEXT


def test_corrupt_only_allowed_operations():
    for seed in range(20):
        out = corrupt_text(TEXT, random.Random(seed))
        allowed = set(TEXT) | set(CONFUSABLES.values())
        assert set(out) <= allowed
        assert len(out) <= 500


def test_corrupt_short_returns_truncated():
    assert corrupt_text("abc", random.Random(1)) == "abc"


def test_should_mock_chance_zero():
    s = Settings(chat_id=1, mock_chance=0)
    assert not should_mock(s, 5, NOW, None, set(), random.Random(1))


def test_should_mock_targets_mode():
    s = Settings(chat_id=1, mock_chance=100, mock_cooldown_min=0, mock_mode="targets")
    assert not should_mock(s, 5, NOW, None, {7}, random.Random(1))
    assert should_mock(s, 7, NOW, None, {7}, random.Random(1))


def test_should_mock_cooldown():
    s = Settings(chat_id=1, mock_chance=100, mock_cooldown_min=10)
    last = NOW - timedelta(minutes=9)
    assert not should_mock(s, 5, NOW, last, set(), random.Random(1))
    assert should_mock(s, 5, NOW, NOW - timedelta(minutes=11), set(), random.Random(1))


def test_should_mock_all_mode_ignores_targets():
    s = Settings(chat_id=1, mock_chance=100, mock_cooldown_min=0)
    assert should_mock(s, 999, NOW, None, set(), random.Random(1))
