import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

from bot.handlers.mock import build_mock_router
from bot.personality import Personality
from bot.db import connect
from bot.storage import Storage

NOW = datetime(2026, 11, 10, 12, 0, tzinfo=timezone(timedelta(hours=3)))


def _build(tmp_path):
    conn = connect(tmp_path / "t.db")
    storage = Storage(conn)
    personality = Personality(Path(__file__).parent.parent / "bot" / "characters",
                              rng=random.Random(1))
    return build_mock_router(storage, personality, "Europe/Moscow", rng=random.Random(1))


def test_router_builds(tmp_path):
    router = _build(tmp_path)
    assert router is not None
