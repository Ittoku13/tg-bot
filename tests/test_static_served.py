import random
from pathlib import Path

from fastapi.testclient import TestClient

from bot.config import Config
from bot.db import connect
from bot.personality import Personality
from bot.storage import Storage
from bot.webapp.app import create_app


def test_static_index_served(tmp_path):
    conn = connect(tmp_path / "t.db")
    storage = Storage(conn)
    personality = Personality(Path(__file__).parent.parent / "bot" / "characters",
                              rng=random.Random(1))
    config = Config(bot_token="123:fake", superadmin_id=7,
                    webapp_domain="x.example.com", chat_id=-1,
                    data_dir=tmp_path, timezone="Europe/Moscow")
    client = TestClient(create_app(object(), storage, personality, config))
    r = client.get("/")
    assert r.status_code == 200
    assert "tg-bot admin" in r.text
