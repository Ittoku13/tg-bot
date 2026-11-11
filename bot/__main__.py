import asyncio
import logging
import random
import shutil
from datetime import datetime
from pathlib import Path

import uvicorn
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand, ErrorEvent, Message

from bot.config import Config, load_config
from bot.db import connect
from bot.handlers.admin import build_admin_router
from bot.handlers.game import build_game_router
from bot.handlers.mock import build_mock_router
from bot.handlers.video import build_video_router
from bot.personality import Personality
from bot.scheduler import run_scheduler
from bot.storage import Storage
from bot.webapp.app import create_app

log = logging.getLogger(__name__)


def setup_logging(data_dir: Path) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(data_dir / "bot.log", encoding="utf-8"),
        ],
    )


def create_dispatcher(config: Config, storage: Storage,
                      personality: Personality, bot: Bot) -> Dispatcher:
    dp = Dispatcher()
    rng = random.Random()

    async def track_user(handler, event, data):
        msg = event if isinstance(event, Message) else None
        if msg and msg.chat.type in {"group", "supergroup"} and msg.from_user:
            storage.upsert_user(
                msg.chat.id, msg.from_user.id,
                msg.from_user.username, msg.from_user.first_name,
                datetime.now(),
            )
        return await handler(event, data)

    dp.message.middleware(track_user)

    dp.include_router(build_admin_router(bot, storage, personality, config))
    dp.include_router(build_game_router(storage, personality))
    dp.include_router(build_video_router(bot, storage, personality, config))
    dp.include_router(build_mock_router(storage, personality, config.timezone, rng))

    @dp.error()
    async def on_error(event: ErrorEvent) -> None:
        log.error("update failed: %r", event.exception, exc_info=event.exception)

    return dp


def cleanup_tmp(tmp: Path) -> None:
    if not tmp.exists():
        return
    for f in tmp.glob("**/*"):
        if f.is_dir():
            shutil.rmtree(f, ignore_errors=True)
        else:
            f.unlink(missing_ok=True)


async def configure_bot(bot: Bot) -> None:
    await bot.delete_webhook(drop_pending_updates=False)
    await bot.set_my_commands([
        BotCommand(command="rating", description="Рейтинг «Олега дня»"),
        BotCommand(command="mystats", description="Моя статистика"),
        BotCommand(command="character", description="Характер бота (админы)"),
        BotCommand(command="admin", description="Админка (админы)"),
    ])
    log.info("telegram webhook disabled and bot commands registered")


async def amain() -> None:
    config = load_config()
    setup_logging(Path(config.data_dir))
    conn = connect(Path(config.data_dir) / "bot.db")
    storage = Storage(conn)
    personality = Personality(Path(__file__).parent / "characters")
    bot = Bot(token=config.bot_token)
    dp = create_dispatcher(config, storage, personality, bot)

    webapp = create_app(bot, storage, personality, config)
    server = uvicorn.Server(uvicorn.Config(webapp, host="0.0.0.0", port=8080,
                                           log_level="info"))
    tmp = Path(config.data_dir) / "tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    cleanup_tmp(tmp)

    await configure_bot(bot)

    log.info("starting bot (polling) + webapp (:8080)")
    await asyncio.gather(
        dp.start_polling(bot),
        server.serve(),
        run_scheduler(bot, storage, personality, config.timezone),
    )


if __name__ == "__main__":
    asyncio.run(amain())
