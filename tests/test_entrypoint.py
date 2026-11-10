import random
from pathlib import Path

from aiogram import Bot

from bot.__main__ import cleanup_tmp, create_dispatcher
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
