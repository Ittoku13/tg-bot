import asyncio
import random
from pathlib import Path

import pytest
from aiogram import Bot
from aiogram.methods import DeleteWebhook, SendMessage, SetMyCommands
from aiogram.types import Update

from bot.__main__ import cleanup_tmp, configure_bot, create_dispatcher
from bot.config import Config
from bot.db import connect
from bot.personality import Personality
from bot.storage import Storage


def test_create_dispatcher(tmp_path):
    conn = connect(tmp_path / "t.db")
    storage = Storage(conn)
    personality = Personality(Path(__file__).parent.parent / "bot" / "characters",
                              rng=random.Random(1))
    config = Config(bot_token="123:fake", superadmin_id=7,
                    webapp_domain="x.example.com", chat_id=-1,
                    data_dir=tmp_path, timezone="Europe/Moscow")
    bot = Bot(token="123:fake")
    dp = create_dispatcher(config, storage, personality, bot)
    assert dp is not None


class FakeSession:
    def __init__(self):
        self.methods = []

    async def __call__(self, bot, method, timeout=None):
        self.methods.append(method)
        return True


@pytest.fixture()
def dispatcher_context(tmp_path):
    conn = connect(tmp_path / "updates.db")
    storage = Storage(conn)
    personality = Personality(Path(__file__).parent.parent / "bot" / "characters",
                              rng=random.Random(1))
    config = Config(bot_token="123:fake", superadmin_id=7,
                    webapp_domain="x.example.com", chat_id=-100500,
                    data_dir=tmp_path, timezone="Europe/Moscow")
    session = FakeSession()
    bot = Bot(token="123:fake", session=session)
    dp = create_dispatcher(config, storage, personality, bot)
    yield dp, storage, bot, session
    conn.close()


def message_update(bot, text, chat_type="private"):
    chat_id = -100500 if chat_type == "supergroup" else 42
    message = {
        "message_id": 1,
        "date": 1700000000,
        "chat": {"id": chat_id, "type": chat_type},
        "from": {"id": 42, "is_bot": False, "first_name": "User"},
        "text": text,
    }
    if text.startswith("/"):
        message["entities"] = [{"type": "bot_command", "offset": 0,
                                "length": len(text)}]
    return Update.model_validate({"update_id": 1, "message": message},
                                 context={"bot": bot})


def test_configure_bot_disables_webhook(dispatcher_context):
    _, _, bot, session = dispatcher_context
    asyncio.run(configure_bot(bot))
    assert isinstance(session.methods[0], DeleteWebhook)
    assert session.methods[0].drop_pending_updates is False
    assert isinstance(session.methods[1], SetMyCommands)


@pytest.mark.parametrize("command", ["/start", "/rating", "/mystats"])
def test_commands_send_answers(dispatcher_context, command):
    dp, _, bot, session = dispatcher_context
    asyncio.run(dp.feed_update(bot, message_update(bot, command)))
    sent = [m for m in session.methods if isinstance(m, SendMessage)]
    assert len(sent) == 1
    assert sent[0].chat_id == 42
    assert sent[0].text


def test_group_message_is_tracked_and_mocked(dispatcher_context):
    dp, storage, bot, session = dispatcher_context
    storage.update_settings(-100500, mock_chance=100, mock_cooldown_min=0)
    text = "Я эйчар и запрещаю удалёнку и гибрид для всех сотрудников"
    update = message_update(bot, text, chat_type="supergroup")
    asyncio.run(dp.feed_update(bot, update))
    sent = [m for m in session.methods if isinstance(m, SendMessage)]
    assert len(sent) == 1
    assert sent[0].text != text
    assert [u.user_id for u in storage.list_users(-100500)] == [42]


def test_cleanup_tmp_removes_subdirs(tmp_path):
    sub = tmp_path / "tmp" / "-1_100"
    sub.mkdir(parents=True)
    (sub / "video.mp4").write_bytes(b"x")
    (tmp_path / "tmp" / "file.txt").write_text("y")
    cleanup_tmp(tmp_path / "tmp")
    assert not (tmp_path / "tmp" / "-1_100").exists()
    assert not (tmp_path / "tmp" / "file.txt").exists()


def test_cleanup_tmp_missing_dir_noop(tmp_path):
    cleanup_tmp(tmp_path / "nope")  # must not raise
