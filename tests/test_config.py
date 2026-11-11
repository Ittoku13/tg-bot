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
        "VIDEO_MAX_SIZE_MB": "50",
        "VIDEO_MAX_DURATION_SECONDS": "300",
    })
    assert cfg.bot_token == "123:fake"
    assert cfg.superadmin_id == 42
    assert cfg.chat_id == -100500
    assert cfg.webapp_domain == "admin.example.com"
    assert cfg.data_dir.as_posix() == "/tmp/tg-bot-data"
    assert cfg.timezone == "Europe/Moscow"
    assert cfg.webapp_url == "https://admin.example.com"
    assert cfg.video_max_size_mb == 50
    assert cfg.video_max_duration_seconds == 300


def test_load_config_defaults():
    cfg = load_config({"BOT_TOKEN": "123:fake"})
    assert cfg.superadmin_id is None
    assert cfg.chat_id is None
    assert cfg.webapp_domain == "localhost"
    assert cfg.timezone == "Europe/Moscow"
    assert cfg.video_max_size_mb == 48
    assert cfg.video_max_duration_seconds == 600


@pytest.mark.parametrize("key", ["VIDEO_MAX_SIZE_MB", "VIDEO_MAX_DURATION_SECONDS"])
@pytest.mark.parametrize("value", ["0", "-1"])
def test_video_limits_must_be_positive(key, value):
    with pytest.raises(ValueError, match=key):
        load_config({"BOT_TOKEN": "123:fake", key: value})


def test_missing_token_raises():
    with pytest.raises(RuntimeError, match="BOT_TOKEN"):
        load_config({})
