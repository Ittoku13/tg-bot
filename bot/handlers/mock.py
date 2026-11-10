import random
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.types import Message

from bot.personality import Personality
from bot.services.downloader import extract_video_url
from bot.services.mockery import corrupt_text, is_mockable, should_mock
from bot.storage import Storage


def build_mock_router(storage: Storage, personality: Personality, tz_name: str,
                      rng: random.Random | None = None) -> Router:
    router = Router()
    rng = rng or random.Random()
    tz = ZoneInfo(tz_name)

    @router.message(F.text.func(lambda t: not t or extract_video_url(t) is None))
    async def on_message(message: Message) -> None:
        text = message.text or ""
        if not text or not is_mockable(text):
            return
        chat_id = message.chat.id
        author_id = message.from_user.id if message.from_user else 0
        settings = storage.settings(chat_id)
        targets = storage.mock_targets(chat_id) if settings.mock_mode == "targets" else set()
        now = datetime.now(tz)
        if not should_mock(settings, author_id, now,
                           storage.last_mock_at(chat_id), targets, rng):
            return
        corrupted = corrupt_text(text, rng)
        if not corrupted.strip():
            return
        await message.reply(corrupted)
        storage.set_last_mock(chat_id, now)

    return router
