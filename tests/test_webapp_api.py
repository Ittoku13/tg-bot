import json
import random
import time
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from bot.config import Config
from bot.db import connect
from bot.personality import Personality
from bot.storage import Storage
from bot.webapp.app import create_app

CHAT_ID = -100500
MSK = timezone(timedelta(hours=3))
NOW = datetime(2026, 11, 10, 12, 0, tzinfo=MSK)


class FakeChatMember:
    def __init__(self, status):
        self.status = status


class FakeBot:
    async def get_chat_member(self, chat_id, user_id):
        return FakeChatMember("administrator" if user_id == 42 else "member")


def make_init_data(user_id: int, token: str = "123:fake") -> str:
    import hashlib
    import hmac
    pairs = {"user": json.dumps({"id": user_id}), "auth_date": str(int(time.time()))}
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    pairs["hash"] = hmac.new(secret, data_check_string.encode(), hashlib.sha256).hexdigest()
    return urllib.parse.urlencode(pairs)


@pytest.fixture()
def client(tmp_path):
    conn = connect(tmp_path / "t.db")
    storage = Storage(conn)
    storage.upsert_user(CHAT_ID, 42, "admin", "Админ", NOW)
    storage.upsert_user(CHAT_ID, 43, "user", "Юзер", NOW)
    storage.settings(CHAT_ID)
    personality = Personality(Path(__file__).parent.parent / "bot" / "characters",
                              rng=random.Random(1))
    config = Config(bot_token="123:fake", superadmin_id=7,
                    webapp_domain="admin.example.com", chat_id=CHAT_ID,
                    data_dir=tmp_path, timezone="Europe/Moscow")
    app = create_app(FakeBot(), storage, personality, config)
    test_client = TestClient(app)
    test_client.headers["X-Telegram-Init-Data"] = make_init_data(42)
    yield test_client
    conn.close()


def test_state(client):
    r = client.get("/api/state")
    assert r.status_code == 200
    body = r.json()
    assert body["settings"]["character"] == "clean"
    assert {u["user_id"] for u in body["known_users"]} == {42, 43}


def test_update_character(client):
    r = client.post("/api/character", json={"character": "adult"})
    assert r.status_code == 200
    assert r.json()["settings"]["character"] == "adult"
    assert client.get("/api/state").json()["settings"]["character"] == "adult"


def test_validation_error_422(client):
    r = client.post("/api/mock", json={"mock_chance": 150})
    assert r.status_code == 422


def test_mock_targets_replace(client):
    r = client.post("/api/mock_targets", json={"user_ids": [42, 42, 43]})
    assert r.status_code == 200
    assert set(client.get("/api/state").json()["mock_targets"]) == {42, 43}
    client.post("/api/mock_targets", json={"user_ids": [43]})
    assert client.get("/api/state").json()["mock_targets"] == [43]


def test_reset_rating(client):
    r = client.post("/api/reset_rating")
    assert r.status_code == 200


def test_unauthorized(client):
    del client.headers["X-Telegram-Init-Data"]
    assert client.get("/api/state").status_code == 401
    client.headers["X-Telegram-Init-Data"] = make_init_data(43)  # member, not admin
    assert client.get("/api/state").status_code == 403
    client.headers["X-Telegram-Init-Data"] = "garbage"
    assert client.get("/api/state").status_code == 401
