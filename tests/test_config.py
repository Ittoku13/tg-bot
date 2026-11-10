import pytest

from bot.config import Config, load_config


def test_load_config_full():
    cfg = load_config({
        "BOT_TOKEN": "123:fake",
        "SUPERADMIN_ID": "42",
        "CHAT_ID": "-100500",
        "WEBAPP_DOMAIN": "admin.example.com",
        "DATA_DIR": "/tmp/tg-bot-data",
        "TZ": "Europe/Moscow",
    })
    assert cfg.bot_token == "123:fake"
    assert cfg.superadmin_id == 42
    assert cfg.chat_id == -100500
    assert cfg.webapp_domain == "admin.example.com"
    assert cfg.data_dir.as_posix() == "/tmp/tg-bot-data"
    assert cfg.timezone == "Europe/Moscow"
    assert cfg.webapp_url == "https://admin.example.com"


def test_load_config_defaults():
    cfg = load_config({"BOT_TOKEN": "123:fake"})
    assert cfg.superadmin_id is None
    assert cfg.chat_id is None
    assert cfg.webapp_domain == "localhost"
    assert cfg.timezone == "Europe/Moscow"


def test_missing_token_raises():
    with pytest.raises(RuntimeError, match="BOT_TOKEN"):
        load_config({})
