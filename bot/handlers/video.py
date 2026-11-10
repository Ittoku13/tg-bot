import asyncio
import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.types import FSInputFile, Message

from bot.config import Config
from bot.personality import Personality
from bot.services.downloader import (UrlCache, VideoError, VideoTooBig,
                                     extract_video_url, process_video)
from bot.storage import Storage

log = logging.getLogger(__name__)


def cleanup_workdirs(data_dir: Path, chat_id: int) -> None:
    tmp = Path(data_dir) / "tmp"
    if not tmp.exists():
        return
    for d in tmp.glob(f"{chat_id}_*"):
        if not d.is_dir():
            continue
        for f in sorted(d.glob("**/*"), reverse=True):
            f.unlink(missing_ok=True)
        d.rmdir()


def build_video_router(bot, storage: Storage, personality: Personality,
                       config: Config) -> Router:
    router = Router()
    cache = UrlCache()
    semaphores: dict[int, asyncio.Semaphore] = {}
    global_sem = asyncio.Semaphore(2)

    def sem(chat_id: int) -> asyncio.Semaphore:
        return semaphores.setdefault(chat_id, asyncio.Semaphore(1))

    @router.message(F.text.func(lambda t: bool(t) and extract_video_url(t) is not None))
    async def on_video_link(message: Message) -> None:
        url = extract_video_url(message.text or "")
        if not url:
            return
        chat_id = message.chat.id
        tz = ZoneInfo(config.timezone)
        now = datetime.now(tz)
        if cache.seen_recently(chat_id, url, now):
            return
        cache.mark(chat_id, url, now)
        async with sem(chat_id):
            async with global_sem:
                await _process(message, url, chat_id)

    async def _process(message: Message, url: str, chat_id: int) -> None:
        settings = storage.settings(chat_id)
        workdir = Path(config.data_dir) / "tmp" / f"{chat_id}_{message.message_id}"
        cookies = Path(config.data_dir) / "cookies.txt"
        try:
            await bot.send_chat_action(chat_id, "upload_video")
            video = await process_video(
                url, workdir, cookies if cookies.exists() else None)
            await message.answer_video(
                FSInputFile(video),
                caption=personality.phrase(settings.character, "video_ok",
                                           title=video.stem, url=url),
                reply_to_message_id=message.message_id,
            )
        except VideoTooBig:
            await message.answer(
                personality.phrase(settings.character, "video_too_big", url=url),
                reply_to_message_id=message.message_id)
        except VideoError as e:
            log.info("video failed: %s", e.reason)
            await message.answer(
                personality.phrase(settings.character, "video_fail",
                                   reason=e.reason[:100], url=url),
                reply_to_message_id=message.message_id)
        finally:
            cleanup_workdirs(config.data_dir, chat_id)

    return router
