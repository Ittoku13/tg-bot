import random
from datetime import datetime, timedelta

from bot.storage import Settings

CONFUSABLES: dict[str, str] = {
    "р": "л", "л": "р", "с": "з", "з": "с", "е": "и", "ё": "е", "и": "е",
    "о": "а", "а": "о", "т": "ч", "ч": "т", "б": "п", "п": "б", "д": "т",
    "н": "м", "м": "н", "в": "ф", "ф": "в", "г": "к", "к": "г", "у": "ю",
    "ь": "ъ", "ъ": "ь",
}

MAX_MOCK_LENGTH = 500
MIN_MOCKABLE_LEN = 10


def is_mockable(text: str) -> bool:
    return len(text.strip()) >= MIN_MOCKABLE_LEN


def corrupt_text(text: str, rng: random.Random) -> str:
    chars = list(text)
    mappable = [i for i, ch in enumerate(chars) if ch.lower() in CONFUSABLES]
    if not mappable:
        return text[:MAX_MOCK_LENGTH]
    target = max(1, int(len(mappable) * 0.15))
    ops = 0
    for idx in mappable:
        if ops >= target:
            break
        if rng.random() >= 0.5:
            continue
        ch = chars[idx]
        repl = CONFUSABLES[ch.lower()]
        roll = rng.random()
        if roll < 0.70:
            chars[idx] = repl.upper() if ch.isupper() else repl
        elif roll < 0.85:
            chars[idx] = ""
        elif idx + 1 < len(chars) and chars[idx + 1].isalpha():
            chars[idx], chars[idx + 1] = chars[idx + 1], chars[idx]
        ops += 1
    return "".join(chars)[:MAX_MOCK_LENGTH]


def should_mock(settings: Settings, author_id: int, now: datetime,
                last_mock_at: datetime | None, targets: set[int],
                rng: random.Random) -> bool:
    if settings.mock_chance <= 0:
        return False
    if settings.mock_mode == "targets" and author_id not in targets:
        return False
    if last_mock_at is not None:
        if now - last_mock_at < timedelta(minutes=settings.mock_cooldown_min):
            return False
    return rng.random() * 100 < settings.mock_chance
