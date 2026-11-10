import asyncio
import logging
import random
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from bot.personality import Personality
from bot.services.picker import pick_candidate
from bot.storage import Storage

log = logging.getLogger(__name__)


def next_pick_time(now: datetime, pick_time: str, tz_name: str) -> datetime:
    tz = ZoneInfo(tz_name)
    hh, mm = map(int, pick_time.split(":"))
    local_now = now.astimezone(tz)
    candidate = local_now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if candidate <= local_now:
        candidate += timedelta(days=1)
    return candidate


async def run_scheduler(bot, storage: Storage, personality: Personality,
                        tz_name: str, poll_seconds: float = 30.0) -> None:
    tz = ZoneInfo(tz_name)
    rng = random.Random()
    while True:
        try:
            await asyncio.sleep(poll_seconds)
            now = datetime.now(tz)
            for chat_id in storage.chat_ids_with_auto_pick():
                try:
                    await _maybe_pick(bot, storage, personality, chat_id, now, tz, rng)
                except Exception:
                    log.exception("auto-pick failed for chat %s", chat_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("scheduler iteration failed")


async def _maybe_pick(bot, storage: Storage, personality: Personality,
                      chat_id: int, now: datetime, tz, rng) -> None:
    settings = storage.settings(chat_id)
    hh, mm = map(int, settings.pick_time.split(":"))
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if (now.hour, now.minute) < (hh, mm):
        return
    last = storage.last_pick(chat_id)
    if last is not None and last[1] >= start_of_day:
        return
    last_user_id = last[0] if last else None
    candidate = pick_candidate(storage.list_users(chat_id), last_user_id,
                               settings.exclude_last, rng)
    if candidate is None:
        log.info("no candidates for chat %s", chat_id)
        return
    storage.add_pick(chat_id, candidate.user_id, now)
    await bot.send_message(
        chat_id,
        personality.phrase(settings.character, "pick",
                           name=candidate.display_name, role=settings.role_name),
    )
