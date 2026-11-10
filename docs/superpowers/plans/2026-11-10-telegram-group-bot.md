# Telegram Group Bot — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Telegram-бот для группы: игра «Олег дня» с рейтингом, два характера текстов, мок-ответы с искажением букв, скачивание YouTube/Instagram видео с обжатием, мини-апп админка, docker compose деплой.

**Architecture:** Монолит на Python 3.12: aiogram 3 (long polling) + FastAPI (мини-апп, in-process) + SQLite в одном asyncio-процессе. Хендлеры тонкие, вся логика — в чистых функциях сервисов (тестируются без сети и Telegram). План реализуется строго по порядку; каждая задача заканчивается зелёными тестами и коммитом.

**Tech Stack:** Python 3.12+, aiogram 3.x, FastAPI + uvicorn, SQLite (stdlib `sqlite3`), yt-dlp, ffmpeg (subprocess), PyYAML, pytest.

**Spec:** `docs/superpowers/specs/2026-11-10-telegram-group-bot-design.md`

## Global Constraints

- Python 3.12+, зависимости только из `requirements.txt` / `requirements-dev.txt`.
- Часовой пояс по умолчанию: `Europe/Moscow` (env `TZ`).
- Лимит размера видео на отправку: 48 МБ (`SIZE_LIMIT_BYTES = 48 * 1024 * 1024`), Bot API лимит 50 МБ.
- Лимит длины мок-ответа: 500 символов.
- Фильтр видео-ссылок (строго): `youtu.be/<id>`, `youtube.com/watch`, `youtube.com/shorts/<id>`, `instagram.com/(reel|reels|p)/<slug>`.
- Мок-ответы: `mock_chance` по умолчанию 3 (%), `mock_cooldown_min` по умолчанию 10 (мин), режимы `all` | `targets`.
- Характеры: `clean`, `adult`. События в YAML: `pick`, `video_ok`, `video_fail`, `video_too_big`, `rating_header`, `rating_empty`, `help`, `error`.
- Периоды рейтинга: `all` (всё время), `month` (30 дней), `week` (7 дней).
- Тесты запускаются командой `python -m pytest tests -q` из корня проекта. В тестах запрещены сеть и реальные вызовы Telegram API; токен бота никогда не хардкодим (в тестах `"123:fake"`).
- Коммиты: conventional prefixes (`feat:`, `test:`, `chore:`, `docs:`), русское описание допустимо.
- Каждая задача заканчивается только когда `python -m pytest tests -q` полностью зелёный.

---

### Task 1: Скелет проекта и конфиг

**Files:**
- Create: `requirements.txt`
- Create: `requirements-dev.txt`
- Create: `.env.example`
- Create: `bot/__init__.py` (пустой)
- Create: `bot/config.py`
- Create: `tests/test_config.py`

**Interfaces:**
- Consumes: ничего (первая задача).
- Produces: `bot.config.Config` (frozen dataclass) с полями `bot_token: str`, `superadmin_id: int | None`, `webapp_domain: str`, `chat_id: int | None`, `data_dir: Path`, `timezone: str`; свойство `webapp_url -> str`; функция `load_config(env: Mapping[str, str] | None = None) -> Config` (при `env=None` читает `os.environ`); `Config` кидает `RuntimeError`, если `BOT_TOKEN` отсутствует.

- [ ] **Step 1: Зафиксировать зависимости и пример env**

`requirements.txt`:
```text
aiogram>=3.7,<4
fastapi>=0.115
uvicorn[standard]>=0.30
yt-dlp>=2024.8.6
PyYAML>=6.0.2
```

`requirements-dev.txt`:
```text
-r requirements.txt
pytest>=8.3
httpx>=0.27
```

`.env.example`:
```text
BOT_TOKEN=
SUPERADMIN_ID=
CHAT_ID=
WEBAPP_DOMAIN=
TZ=Europe/Moscow
```

Run: `pip install -r requirements-dev.txt`

- [ ] **Step 2: Написать падающий тест конфига**

`tests/test_config.py`:
```python
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
```

- [ ] **Step 3: Запустить тест, убедиться что падает**

Run: `python -m pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'bot.config'`

- [ ] **Step 4: Реализовать конфиг**

`bot/config.py`:
```python
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class Config:
    bot_token: str
    superadmin_id: int | None
    webapp_domain: str
    chat_id: int | None
    data_dir: Path
    timezone: str

    @property
    def webapp_url(self) -> str:
        return f"https://{self.webapp_domain}"


def load_config(env: Mapping[str, str] | None = None) -> Config:
    env = os.environ if env is None else env
    token = env.get("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN is required")
    return Config(
        bot_token=token,
        superadmin_id=int(env["SUPERADMIN_ID"]) if env.get("SUPERADMIN_ID") else None,
        webapp_domain=env.get("WEBAPP_DOMAIN", "localhost"),
        chat_id=int(env["CHAT_ID"]) if env.get("CHAT_ID") else None,
        data_dir=Path(env.get("DATA_DIR", "data")),
        timezone=env.get("TZ", "Europe/Moscow"),
    )
```

- [ ] **Step 5: Запустить тест, убедиться что проходит**

Run: `python -m pytest tests/test_config.py -v`
Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add requirements.txt requirements-dev.txt .env.example bot/ tests/
git commit -m "chore: project scaffold + config"
```

---

### Task 2: База данных и хранилище

**Files:**
- Create: `bot/db.py`
- Create: `bot/storage.py`
- Create: `tests/test_storage.py`

**Interfaces:**
- Consumes: `bot.config` (нет, самостоятельная задача).
- Produces:
  - `bot.db.connect(path: str | Path) -> sqlite3.Connection` — создаёт файл БД (включая родительские директории), `row_factory = sqlite3.Row`, `PRAGMA journal_mode=WAL`, и сразу применяет `migrate`.
  - `bot.db.migrate(conn) -> None` — создаёт таблицы, ставит `PRAGMA user_version=1`.
  - `bot.storage.Settings` — frozen dataclass: `chat_id: int`, `role_name: str = "Олег"`, `pick_time: str = "12:00"`, `character: str = "clean"`, `auto_pick_enabled: bool = True`, `exclude_last: bool = True`, `mock_chance: int = 3`, `mock_cooldown_min: int = 10`, `mock_mode: str = "all"`.
  - `bot.storage.UserRow` — dataclass: `user_id: int`, `username: str | None`, `first_name: str | None`, `last_active: datetime | None`; свойство `display_name: str` (first_name или @username или "user_<id>").
  - `bot.storage.Storage(conn: sqlite3.Connection)` с методами:
    - `upsert_user(chat_id: int, user_id: int, username: str | None, first_name: str | None, when: datetime) -> None`
    - `list_users(chat_id: int) -> list[UserRow]`
    - `settings(chat_id: int) -> Settings` — **get-or-create**: при отсутствии строки создаёт её с дефолтами (нужно, чтобы `chat_ids_with_auto_pick` видел чаты с настройками по умолчанию)
    - `update_settings(chat_id: int, **fields) -> Settings` — валидация: `character in {"clean","adult"}`, `mock_mode in {"all","targets"}`, `0 <= mock_chance <= 100`, `mock_cooldown_min >= 0`, `pick_time` формат `HH:MM`; невалидное → `ValueError`.
    - `add_pick(chat_id: int, user_id: int, when: datetime) -> None`
    - `last_pick(chat_id: int) -> tuple[int, datetime] | None` — (user_id, when) последнего выбора
    - `last_pick_for(chat_id: int, user_id: int) -> datetime | None` — время последнего выбора конкретного пользователя
    - `clear_picks(chat_id: int) -> None`
    - `top(chat_id: int, period_days: int | None, limit: int = 10) -> list[tuple[int, int]]` — [(user_id, count)], сортировка по count DESC, при равенстве — раньший last pick раньше
    - `count_for(chat_id: int, user_id: int, period_days: int | None) -> int`
    - `replace_mock_targets(chat_id: int, user_ids: list[int]) -> None`
    - `mock_targets(chat_id: int) -> set[int]`
    - `last_mock_at(chat_id: int) -> datetime | None`
    - `set_last_mock(chat_id: int, when: datetime) -> None`
    - `chat_ids_with_auto_pick() -> list[int]`
  - Даты хранятся как ISO-строки (aware datetime, один часовой пояс — сравнение строк корректно).

- [ ] **Step 1: Написать падающие тесты хранилища**

`tests/test_storage.py`:
```python
from datetime import datetime, timedelta, timezone

import pytest

from bot.db import connect
from bot.storage import Settings, Storage

MSK = timezone(timedelta(hours=3))
NOW = datetime(2026, 11, 10, 12, 0, tzinfo=MSK)


@pytest.fixture()
def storage(tmp_path):
    conn = connect(tmp_path / "test.db")
    yield Storage(conn)
    conn.close()


def test_settings_defaults(storage):
    s = storage.settings(-1)
    assert s == Settings(chat_id=-1)


def test_update_settings_roundtrip(storage):
    s = storage.update_settings(-1, role_name="Пчела", pick_time="09:30", character="adult")
    assert s.role_name == "Пчела"
    assert s.pick_time == "09:30"
    assert s.character == "adult"
    assert storage.settings(-1).role_name == "Пчела"


@pytest.mark.parametrize("bad", [
    {"character": "evil"},
    {"mock_mode": "everyone"},
    {"mock_chance": 101},
    {"mock_chance": -1},
    {"mock_cooldown_min": -5},
    {"pick_time": "25:00"},
    {"pick_time": "noon"},
])
def test_update_settings_validation(storage, bad):
    with pytest.raises(ValueError):
        storage.update_settings(-1, **bad)


def test_users_upsert_and_list(storage):
    storage.upsert_user(-1, 10, "oleg", "Олег", NOW)
    storage.upsert_user(-1, 10, "oleg2", "Олег", NOW + timedelta(hours=1))
    storage.upsert_user(-1, 20, None, "Пчела", NOW)
    users = storage.list_users(-1)
    assert [(u.user_id, u.username, u.first_name) for u in users] == [
        (10, "oleg2", "Олег"),
        (20, None, "Пчела"),
    ]


def test_display_name_fallback(storage):
    storage.upsert_user(-1, 30, None, None, NOW)
    assert storage.list_users(-1)[0].display_name == "user_30"
    storage.upsert_user(-1, 31, "bee", None, NOW)
    assert storage.list_users(-1)[1].display_name == "@bee"


def test_picks_top_periods_and_clear(storage):
    day = timedelta(days=1)
    for i in range(3):
        storage.add_pick(-1, 10, NOW - i * day)
    storage.add_pick(-1, 20, NOW - 40 * day)
    assert storage.top(-1, None) == [(10, 3), (20, 1)]
    assert storage.top(-1, 30) == [(10, 3)]
    assert storage.top(-1, 7) == [(10, 3)]
    assert storage.count_for(-1, 20, None) == 1
    assert storage.last_pick(-1) == (10, NOW)
    assert storage.last_pick_for(-1, 20) == NOW - 40 * day
    assert storage.last_pick_for(-1, 99) is None
    storage.clear_picks(-1)
    assert storage.top(-1, None) == []
    assert storage.last_pick(-1) is None


def test_settings_get_or_create(storage):
    assert storage.settings(-1) == Settings(chat_id=-1)
    assert storage.chat_ids_with_auto_pick() == [-1]


def test_top_tie_break_by_earliest_last_pick(storage):
    storage.add_pick(-1, 10, NOW - 5 * timedelta(days=1))
    storage.add_pick(-1, 10, NOW - timedelta(days=1))
    storage.add_pick(-1, 20, NOW - 3 * timedelta(days=1))
    storage.add_pick(-1, 20, NOW - 2 * timedelta(days=1))
    assert storage.top(-1, None) == [(20, 2), (10, 2)]


def test_mock_targets_and_last_mock(storage):
    storage.replace_mock_targets(-1, [1, 2, 2])
    assert storage.mock_targets(-1) == {1, 2}
    storage.replace_mock_targets(-1, [3])
    assert storage.mock_targets(-1) == {3}
    assert storage.last_mock_at(-1) is None
    storage.set_last_mock(-1, NOW)
    assert storage.last_mock_at(-1) == NOW


def test_chat_ids_with_auto_pick(storage):
    storage.settings(-1)
    storage.settings(-2)
    storage.update_settings(-2, auto_pick_enabled=False)
    assert storage.chat_ids_with_auto_pick() == [-1]
```

- [ ] **Step 2: Запустить тесты, убедиться что падают**

Run: `python -m pytest tests/test_storage.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'bot.db'`

- [ ] **Step 3: Реализовать db.py и storage.py**

`bot/db.py`:
```python
import sqlite3
from pathlib import Path

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    chat_id     INTEGER NOT NULL,
    user_id     INTEGER NOT NULL,
    username    TEXT,
    first_name  TEXT,
    last_active TEXT NOT NULL,
    PRIMARY KEY (chat_id, user_id)
);
CREATE TABLE IF NOT EXISTS picks (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id   INTEGER NOT NULL,
    user_id   INTEGER NOT NULL,
    picked_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (
    chat_id           INTEGER PRIMARY KEY,
    role_name         TEXT NOT NULL DEFAULT 'Олег',
    pick_time         TEXT NOT NULL DEFAULT '12:00',
    character         TEXT NOT NULL DEFAULT 'clean',
    auto_pick_enabled INTEGER NOT NULL DEFAULT 1,
    exclude_last      INTEGER NOT NULL DEFAULT 1,
    mock_chance       INTEGER NOT NULL DEFAULT 3,
    mock_cooldown_min INTEGER NOT NULL DEFAULT 10,
    mock_mode         TEXT NOT NULL DEFAULT 'all'
);
CREATE TABLE IF NOT EXISTS mock_targets (
    chat_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    PRIMARY KEY (chat_id, user_id)
);
CREATE TABLE IF NOT EXISTS last_mock (
    chat_id INTEGER PRIMARY KEY,
    at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_picks_chat ON picks (chat_id, picked_at);
"""


def migrate(conn: sqlite3.Connection) -> None:
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version < SCHEMA_VERSION:
        conn.executescript(SCHEMA)
        conn.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
    conn.commit()


def connect(path: str | Path) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    migrate(conn)
    return conn
```

`bot/storage.py`:
```python
import re
import sqlite3
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Any

_PICK_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


@dataclass(frozen=True)
class Settings:
    chat_id: int
    role_name: str = "Олег"
    pick_time: str = "12:00"
    character: str = "clean"
    auto_pick_enabled: bool = True
    exclude_last: bool = True
    mock_chance: int = 3
    mock_cooldown_min: int = 10
    mock_mode: str = "all"


@dataclass(frozen=True)
class UserRow:
    user_id: int
    username: str | None
    first_name: str | None
    last_active: datetime | None

    @property
    def display_name(self) -> str:
        if self.first_name:
            return self.first_name
        if self.username:
            return f"@{self.username}"
        return f"user_{self.user_id}"


class Storage:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    # --- users ---
    def upsert_user(self, chat_id: int, user_id: int, username: str | None,
                    first_name: str | None, when: datetime) -> None:
        self._conn.execute(
            """INSERT INTO users (chat_id, user_id, username, first_name, last_active)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT (chat_id, user_id)
               DO UPDATE SET username=excluded.username,
                             first_name=excluded.first_name,
                             last_active=excluded.last_active""",
            (chat_id, user_id, username, first_name, when.isoformat()),
        )
        self._conn.commit()

    def list_users(self, chat_id: int) -> list[UserRow]:
        rows = self._conn.execute(
            "SELECT * FROM users WHERE chat_id = ? ORDER BY user_id", (chat_id,)
        ).fetchall()
        return [
            UserRow(
                user_id=r["user_id"],
                username=r["username"],
                first_name=r["first_name"],
                last_active=datetime.fromisoformat(r["last_active"]),
            )
            for r in rows
        ]

    # --- settings ---
    def settings(self, chat_id: int) -> Settings:
        row = self._conn.execute(
            "SELECT * FROM settings WHERE chat_id = ?", (chat_id,)
        ).fetchone()
        if row is None:
            self._conn.execute(
                "INSERT INTO settings (chat_id) VALUES (?)", (chat_id,))
            self._conn.commit()
            row = self._conn.execute(
                "SELECT * FROM settings WHERE chat_id = ?", (chat_id,)
            ).fetchone()
        return Settings(
            chat_id=chat_id,
            role_name=row["role_name"],
            pick_time=row["pick_time"],
            character=row["character"],
            auto_pick_enabled=bool(row["auto_pick_enabled"]),
            exclude_last=bool(row["exclude_last"]),
            mock_chance=row["mock_chance"],
            mock_cooldown_min=row["mock_cooldown_min"],
            mock_mode=row["mock_mode"],
        )

    def update_settings(self, chat_id: int, **fields: Any) -> Settings:
        current = self.settings(chat_id)
        updated = replace(current, **fields)
        self._validate(updated)
        self._conn.execute(
            """INSERT INTO settings (chat_id, role_name, pick_time, character,
                                     auto_pick_enabled, exclude_last,
                                     mock_chance, mock_cooldown_min, mock_mode)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT (chat_id) DO UPDATE SET
                   role_name=excluded.role_name,
                   pick_time=excluded.pick_time,
                   character=excluded.character,
                   auto_pick_enabled=excluded.auto_pick_enabled,
                   exclude_last=excluded.exclude_last,
                   mock_chance=excluded.mock_chance,
                   mock_cooldown_min=excluded.mock_cooldown_min,
                   mock_mode=excluded.mock_mode""",
            (updated.chat_id, updated.role_name, updated.pick_time,
             updated.character, int(updated.auto_pick_enabled),
             int(updated.exclude_last), updated.mock_chance,
             updated.mock_cooldown_min, updated.mock_mode),
        )
        self._conn.commit()
        return updated

    @staticmethod
    def _validate(s: Settings) -> None:
        if not s.role_name.strip():
            raise ValueError("role_name must be non-empty")
        if not _PICK_TIME_RE.match(s.pick_time):
            raise ValueError("pick_time must be HH:MM")
        if s.character not in {"clean", "adult"}:
            raise ValueError("character must be 'clean' or 'adult'")
        if s.mock_mode not in {"all", "targets"}:
            raise ValueError("mock_mode must be 'all' or 'targets'")
        if not 0 <= s.mock_chance <= 100:
            raise ValueError("mock_chance must be 0..100")
        if s.mock_cooldown_min < 0:
            raise ValueError("mock_cooldown_min must be >= 0")

    # --- picks ---
    def add_pick(self, chat_id: int, user_id: int, when: datetime) -> None:
        self._conn.execute(
            "INSERT INTO picks (chat_id, user_id, picked_at) VALUES (?, ?, ?)",
            (chat_id, user_id, when.isoformat()),
        )
        self._conn.commit()

    def last_pick(self, chat_id: int) -> tuple[int, datetime] | None:
        row = self._conn.execute(
            "SELECT user_id, picked_at FROM picks WHERE chat_id = ? ORDER BY picked_at DESC, id DESC LIMIT 1",
            (chat_id,),
        ).fetchone()
        if row is None:
            return None
        return row["user_id"], datetime.fromisoformat(row["picked_at"])

    def last_pick_for(self, chat_id: int, user_id: int) -> datetime | None:
        row = self._conn.execute(
            "SELECT picked_at FROM picks WHERE chat_id = ? AND user_id = ? ORDER BY picked_at DESC, id DESC LIMIT 1",
            (chat_id, user_id),
        ).fetchone()
        return datetime.fromisoformat(row["picked_at"]) if row else None

    def clear_picks(self, chat_id: int) -> None:
        self._conn.execute("DELETE FROM picks WHERE chat_id = ?", (chat_id,))
        self._conn.commit()

    def top(self, chat_id: int, period_days: int | None, limit: int = 10) -> list[tuple[int, int]]:
        cutoff = None
        if period_days is not None:
            cutoff = (datetime.now().astimezone() - timedelta(days=period_days)).isoformat()
        where = "chat_id = ?"
        params: list[Any] = [chat_id]
        if cutoff is not None:
            where += " AND picked_at >= ?"
            params.append(cutoff)
        rows = self._conn.execute(
            f"""SELECT user_id, COUNT(*) AS c, MAX(picked_at) AS last_at
                FROM picks WHERE {where}
                GROUP BY user_id
                ORDER BY c DESC, last_at ASC
                LIMIT ?""",
            (*params, limit),
        ).fetchall()
        return [(r["user_id"], r["c"]) for r in rows]

    def count_for(self, chat_id: int, user_id: int, period_days: int | None) -> int:
        cutoff = None
        if period_days is not None:
            cutoff = (datetime.now().astimezone() - timedelta(days=period_days)).isoformat()
        where = "chat_id = ? AND user_id = ?"
        params: list[Any] = [chat_id, user_id]
        if cutoff is not None:
            where += " AND picked_at >= ?"
            params.append(cutoff)
        return int(self._conn.execute(
            f"SELECT COUNT(*) FROM picks WHERE {where}", params
        ).fetchone()[0])

    # --- mock ---
    def replace_mock_targets(self, chat_id: int, user_ids: list[int]) -> None:
        self._conn.execute("DELETE FROM mock_targets WHERE chat_id = ?", (chat_id,))
        self._conn.executemany(
            "INSERT OR IGNORE INTO mock_targets (chat_id, user_id) VALUES (?, ?)",
            [(chat_id, uid) for uid in set(user_ids)],
        )
        self._conn.commit()

    def mock_targets(self, chat_id: int) -> set[int]:
        rows = self._conn.execute(
            "SELECT user_id FROM mock_targets WHERE chat_id = ?", (chat_id,)
        ).fetchall()
        return {r["user_id"] for r in rows}

    def last_mock_at(self, chat_id: int) -> datetime | None:
        row = self._conn.execute(
            "SELECT at FROM last_mock WHERE chat_id = ?", (chat_id,)
        ).fetchone()
        return datetime.fromisoformat(row["at"]) if row else None

    def set_last_mock(self, chat_id: int, when: datetime) -> None:
        self._conn.execute(
            """INSERT INTO last_mock (chat_id, at) VALUES (?, ?)
               ON CONFLICT (chat_id) DO UPDATE SET at=excluded.at""",
            (chat_id, when.isoformat()),
        )
        self._conn.commit()

    def chat_ids_with_auto_pick(self) -> list[int]:
        rows = self._conn.execute(
            "SELECT chat_id FROM settings WHERE auto_pick_enabled = 1"
        ).fetchall()
        return [r["chat_id"] for r in rows]
```

- [ ] **Step 4: Запустить тесты, убедиться что проходят**

Run: `python -m pytest tests/test_storage.py -v`
Expected: все тесты passed (порядка 13)

- [ ] **Step 5: Commit**

```bash
git add bot/db.py bot/storage.py tests/test_storage.py
git commit -m "feat: sqlite storage layer (users, picks, settings, mock targets)"
```

---

### Task 3: Характеры и personality.py

**Files:**
- Create: `bot/characters/clean.yaml`
- Create: `bot/characters/adult.yaml`
- Create: `bot/personality.py`
- Create: `tests/test_personality.py`

**Interfaces:**
- Consumes: ничего.
- Produces: `bot.personality.Personality(characters_dir: Path, rng: random.Random | None = None)` с методами `names() -> list[str]` и `phrase(character: str, event: str, **placeholders: Any) -> str`. Если у персонажа нет события — фолбэк на `clean`; если нет и там — `KeyError`. Плейсхолдеры подставляются через `str.format`.

- [ ] **Step 1: Написать падающий тест**

`tests/test_personality.py`:
```python
import random
from pathlib import Path

import pytest

from bot.personality import Personality

CHARACTERS = Path(__file__).parent.parent / "bot" / "characters"


@pytest.fixture(scope="module")
def personality():
    return Personality(CHARACTERS, rng=random.Random(42))


def test_names_contains_both(personality):
    assert set(personality.names()) == {"clean", "adult"}


def test_phrase_replaces_placeholders(personality):
    text = personality.phrase("clean", "pick", name="Олег", role="Олег")
    assert "{name}" not in text and "{role}" not in text
    assert "Олег" in text


def test_every_event_has_variants(personality):
    events = ["pick", "video_ok", "video_fail", "video_too_big",
              "rating_header", "rating_empty", "help", "error"]
    for name in personality.names():
        for event in events:
            variants = personality._data[name][event]
            assert isinstance(variants, list) and len(variants) >= 1


def test_fallback_to_clean(personality):
    local = Personality(CHARACTERS, rng=random.Random(1))
    local._data["custom"] = {"pick": ["x {name}"]}
    text = local.phrase("custom", "help")
    assert isinstance(text, str) and text
    assert set(personality.names()) == {"clean", "adult"}


def test_missing_event_raises(personality):
    with pytest.raises(KeyError):
        personality.phrase("clean", "no_such_event")
```

- [ ] **Step 2: Запустить тест, убедиться что падает**

Run: `python -m pytest tests/test_personality.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'bot.personality'`

- [ ] **Step 3: Создать YAML-характеры и personality.py**

`bot/characters/clean.yaml`:
```yaml
pick:
  - "Сегодня {role} — {name}! Поздравляем, надежда чата на тебе."
  - "{name}, сегодня ты {role}. Ждём великих дел!"
  - "По результатам строгого жребия звание «{role}» получает {name}!"
video_ok:
  - "Держи: {title}"
  - "Скачал, сжал, отправляю: {title}"
video_fail:
  - "Не смог скачать ({reason}). Возможно, видео приватное или удалено."
  - "Видео недоступно ({reason})."
video_too_big:
  - "Видео слишком длинное — в чат не влезает даже после обжатия."
rating_header:
  - "Топ по званию «{role}» {period}:"
rating_empty:
  - "Пока никто не получал звание. Статистика начнётся с первого выбора."
help:
  - "Команды: /rating — рейтинг, /mystats — моя статистика, /character — характер бота (админы), /admin — админка."
error:
  - "Что-то пошло не так. Попробуй ещё раз."
```

`bot/characters/adult.yaml`:
```yaml
pick:
  - "Сегодня {role} — {name}, блядь. Поздравляю, надежда чата на тебе, не обосрись."
  - "{name}, теперь ты {role}. Вот те крест, ждём великих дел, нахуй."
  - "Строгий жребий решил: «{role}» — {name}. Пиздец, да?"
video_ok:
  - "Держи, братан: {title}"
  - "Скачал и сжал, не благодари: {title}"
video_fail:
  - "Не скачалось ({reason}). Видео, видимо, приватное или его нахер удалили."
  - "Видео недоступно ({reason}), иди разбирайся."
video_too_big:
  - "Видос слишком жирный, в чат не влезает даже после обжатия. Пиздец."
rating_header:
  - "Топ по званию «{role}» {period}:"
rating_empty:
  - "Пусто. Никто ещё не {role}, какие нахуй рейтинги."
help:
  - "Команды: /rating — рейтинг, /mystats — моя статистика, /character — характер бота (админы), /admin — админка."
error:
  - "Что-то пошло по пизде. Попробуй ещё раз."
```

`bot/personality.py`:
```python
import random
from pathlib import Path
from typing import Any

import yaml


class Personality:
    def __init__(self, characters_dir: Path, rng: random.Random | None = None):
        self._rng = rng or random.Random()
        self._data: dict[str, dict[str, list[str]]] = {}
        for path in sorted(Path(characters_dir).glob("*.yaml")):
            self._data[path.stem] = yaml.safe_load(path.read_text(encoding="utf-8"))

    def names(self) -> list[str]:
        return sorted(self._data)

    def phrase(self, character: str, event: str, **placeholders: Any) -> str:
        variants = self._data.get(character, {}).get(event)
        if variants is None:
            variants = self._data["clean"][event]
        return self._rng.choice(variants).format(**placeholders)
```

- [ ] **Step 4: Запустить тесты, убедиться что проходят**

Run: `python -m pytest tests/test_personality.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add bot/characters/ bot/personality.py tests/test_personality.py
git commit -m "feat: personalities (clean/adult) + phrase picker"
```

---

### Task 4: Сервисы игры — picker и rating

**Files:**
- Create: `bot/services/__init__.py` (пустой)
- Create: `bot/services/picker.py`
- Create: `bot/services/rating.py`
- Create: `tests/test_picker.py`
- Create: `tests/test_rating.py`

**Interfaces:**
- Consumes: `bot.storage.UserRow`.
- Produces:
  - `bot.services.picker.pick_candidate(users: list[UserRow], last_user_id: int | None, exclude_last: bool, rng: random.Random) -> UserRow | None`
  - `bot.services.rating.PERIODS: dict[str, int | None]` = `{"all": None, "month": 30, "week": 7}`; `PERIOD_LABELS: dict[str, str]` = `{"all": "за всё время", "month": "за месяц", "week": "за неделю"}`; `period_keys() -> list[str]`
  - `bot.services.rating.format_top(entries: list[tuple[UserRow, int]], period: str, role_name: str) -> str` — первая строка `personality`-стиль не нужен: заголовок текстом «Топ по званию «{role}» {label}:», затем нумерованный список «1. Имя — 5». Бросает `KeyError` при неизвестном period.

- [ ] **Step 1: Написать падающие тесты**

`tests/test_picker.py`:
```python
import random
from datetime import datetime, timedelta, timezone

from bot.services.picker import pick_candidate
from bot.storage import UserRow

NOW = datetime(2026, 11, 10, tzinfo=timezone(timedelta(hours=3)))


def make_users(*ids: int) -> list[UserRow]:
    return [UserRow(user_id=i, username=None, first_name=f"U{i}", last_active=NOW) for i in ids]


def test_picks_from_pool():
    rng = random.Random(1)
    users = make_users(1, 2, 3)
    assert pick_candidate(users, None, False, rng) in users


def test_excludes_last_when_possible():
    rng = random.Random(1)
    users = make_users(1, 2, 3)
    for _ in range(50):
        assert pick_candidate(users, 1, True, rng).user_id != 1


def test_single_user_pool_keeps_last():
    rng = random.Random(1)
    users = make_users(1)
    assert pick_candidate(users, 1, True, rng).user_id == 1


def test_empty_pool_returns_none():
    rng = random.Random(1)
    assert pick_candidate([], None, False, rng) is None
```

`tests/test_rating.py`:
```python
from datetime import datetime, timedelta, timezone

import pytest

from bot.services.rating import PERIODS, format_top, period_keys
from bot.storage import UserRow

NOW = datetime(2026, 11, 10, tzinfo=timezone(timedelta(hours=3)))


def user(uid: int) -> UserRow:
    return UserRow(user_id=uid, username=None, first_name=f"User{uid}", last_active=NOW)


def test_periods_mapping():
    assert PERIODS == {"all": None, "month": 30, "week": 7}
    assert set(period_keys()) == {"all", "month", "week"}


def test_format_top():
    text = format_top([(user(1), 5), (user(2), 2)], "month", "Олег")
    assert "Топ по званию «Олег» за месяц:" in text
    assert "1. User1 — 5" in text
    assert "2. User2 — 2" in text


def test_format_top_unknown_period():
    with pytest.raises(KeyError):
        format_top([], "year", "Олег")
```

- [ ] **Step 2: Запустить тесты, убедиться что падают**

Run: `python -m pytest tests/test_picker.py tests/test_rating.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'bot.services'`

- [ ] **Step 3: Реализовать сервисы**

`bot/services/__init__.py`: пустой файл.

`bot/services/picker.py`:
```python
import random

from bot.storage import UserRow


def pick_candidate(users: list[UserRow], last_user_id: int | None,
                   exclude_last: bool, rng: random.Random) -> UserRow | None:
    pool = list(users)
    if exclude_last and last_user_id is not None and len(pool) > 1:
        pool = [u for u in pool if u.user_id != last_user_id]
    if not pool:
        return None
    return rng.choice(pool)
```

`bot/services/rating.py`:
```python
from bot.storage import UserRow

PERIODS: dict[str, int | None] = {"all": None, "month": 30, "week": 7}
PERIOD_LABELS: dict[str, str] = {
    "all": "за всё время",
    "month": "за месяц",
    "week": "за неделю",
}


def period_keys() -> list[str]:
    return list(PERIODS)


def format_top(entries: list[tuple[UserRow, int]], period: str, role_name: str) -> str:
    label = PERIOD_LABELS[period]
    lines = [f"Топ по званию «{role_name}» {label}:"]
    for i, (u, count) in enumerate(entries, 1):
        lines.append(f"{i}. {u.display_name} — {count}")
    return "\n".join(lines)
```

- [ ] **Step 4: Запустить тесты, убедиться что проходят**

Run: `python -m pytest tests/test_picker.py tests/test_rating.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add bot/services/ tests/test_picker.py tests/test_rating.py
git commit -m "feat: candidate picker + rating formatting"
```

---

### Task 5: Планировщик автовыбора

**Files:**
- Create: `bot/scheduler.py`
- Create: `tests/test_scheduler.py`

**Interfaces:**
- Consumes: `bot.storage.Storage`, `bot.services.picker.pick_candidate`, `bot.personality.Personality`.
- Produces:
  - `bot.scheduler.next_pick_time(now: datetime, pick_time: str, tz_name: str) -> datetime` — ближайшее локальное время `HH:MM` в `tz_name` строго после `now`.
  - `bot.scheduler.run_scheduler(bot, storage: Storage, personality: Personality, tz_name: str, poll_seconds: float = 30.0) -> None` — вечный цикл: для каждого `chat_ids_with_auto_pick()`, если сегодня ещё не было выбора и локальное время >= pick_time — выполнить выбор (pick_candidate по `list_users`, `add_pick`, `send_message` с фразой `pick`). Ошибки одного чата логируются и не прерывают цикл.

- [ ] **Step 1: Написать падающие тесты**

`tests/test_scheduler.py`:
```python
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from bot.scheduler import next_pick_time
from bot.db import connect
from bot.storage import Storage

MSK = ZoneInfo("Europe/Moscow")


def test_next_pick_time_same_day():
    now = datetime(2026, 11, 10, 9, 0, tzinfo=MSK)
    assert next_pick_time(now, "12:00", "Europe/Moscow") == datetime(2026, 11, 10, 12, 0, tzinfo=MSK)


def test_next_pick_time_next_day_when_passed():
    now = datetime(2026, 11, 10, 13, 0, tzinfo=MSK)
    assert next_pick_time(now, "12:00", "Europe/Moscow") == datetime(2026, 11, 11, 12, 0, tzinfo=MSK)


def test_next_pick_time_equal_is_next_day():
    now = datetime(2026, 11, 10, 12, 0, tzinfo=MSK)
    assert next_pick_time(now, "12:00", "Europe/Moscow") == datetime(2026, 11, 11, 12, 0, tzinfo=MSK)


def test_next_pick_time_another_tz():
    utc = timezone.utc
    now = datetime(2026, 11, 10, 8, 30, tzinfo=utc)  # 11:30 МСК
    result = next_pick_time(now, "12:00", "Europe/Moscow")
    assert result.astimezone(MSK) == datetime(2026, 11, 10, 12, 0, tzinfo=MSK)
```

- [ ] **Step 2: Запустить тесты, убедиться что падают**

Run: `python -m pytest tests/test_scheduler.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'bot.scheduler'`

- [ ] **Step 3: Реализовать планировщик**

`bot/scheduler.py`:
```python
import asyncio
import logging
import random
from datetime import datetime
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
```

- [ ] **Step 4: Запустить тесты, убедиться что проходят**

Run: `python -m pytest tests/test_scheduler.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add bot/scheduler.py tests/test_scheduler.py
git commit -m "feat: daily auto-pick scheduler"
```

---

### Task 6: Хендлеры игры (/rating, /mystats)

**Files:**
- Create: `bot/handlers/__init__.py` (пустой)
- Create: `bot/handlers/game.py`
- Create: `tests/test_game_format.py`

**Interfaces:**
- Consumes: `bot.storage.Storage`, `bot.personality.Personality`, `bot.services.rating` (Task 4).
- Produces: `bot.handlers.game.build_game_router(storage: Storage, personality: Personality) -> aiogram.Router` — команды `/rating` (топ-10 за всё время + inline-кнопки периодов с callback-префиксом `rating:`) и `/mystats` (личный счёт за всё время и последняя дата). Форматирование через `rating.format_top`; пустой топ → фраза `rating_empty`.

- [ ] **Step 1: Написать тест форматирования личной статистики**

`tests/test_game_format.py`:
```python
from datetime import datetime, timedelta, timezone

from bot.storage import UserRow

MSK = timezone(timedelta(hours=3))


def format_mystats(user: UserRow, role_name: str, count: int,
                   last: datetime | None) -> str:
    from bot.handlers.game import mystats_text
    return mystats_text(user, role_name, count, last)


def test_mystats_with_history():
    last = datetime(2026, 11, 1, 12, 0, tzinfo=MSK)
    text = format_mystats(UserRow(1, None, "Олег", last), "Олег", 3, last)
    assert "3" in text and "Олег" in text and "2026-11-01" in text


def test_mystats_zero():
    text = format_mystats(UserRow(1, None, "Олег", None), "Олег", 0, None)
    assert "0" in text
```

- [ ] **Step 2: Запустить тест, убедиться что падает**

Run: `python -m pytest tests/test_game_format.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'bot.handlers.game'`

- [ ] **Step 3: Реализовать хендлеры**

`bot/handlers/__init__.py`: пустой файл.

`bot/handlers/game.py`:
```python
from datetime import datetime

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.personality import Personality
from bot.services.rating import PERIODS, format_top, period_keys
from bot.storage import Storage, UserRow


def mystats_text(user: UserRow, role_name: str, count: int, last: datetime | None) -> str:
    last_str = last.date().isoformat() if last else "—"
    return (f"{user.display_name}, звание «{role_name}» получено раз: {count}.\n"
            f"Последний раз: {last_str}")


def _period_kb() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="Всё время", callback_data="rating:all"),
         InlineKeyboardButton(text="Месяц", callback_data="rating:month"),
         InlineKeyboardButton(text="Неделя", callback_data="rating:week")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_game_router(storage: Storage, personality: Personality) -> Router:
    router = Router()

    async def send_rating(target, period: str) -> None:
        is_callback = isinstance(target, CallbackQuery)
        chat_id = target.message.chat.id if is_callback else target.chat.id
        settings = storage.settings(chat_id)
        users = {u.user_id: u for u in storage.list_users(chat_id)}
        entries = [(users[uid], c) for uid, c in storage.top(chat_id, PERIODS[period])
                   if uid in users]
        if not entries:
            text = personality.phrase(settings.character, "rating_empty",
                                      role=settings.role_name)
        else:
            text = format_top(entries, period, settings.role_name)
        if is_callback:
            await target.message.edit_text(text, reply_markup=_period_kb())
        else:
            await target.answer(text, reply_markup=_period_kb())

    @router.message(Command("rating"))
    async def cmd_rating(message: Message) -> None:
        await send_rating(message, "all")

    @router.callback_query(F.data.startswith("rating:"))
    async def cb_rating(query: CallbackQuery) -> None:
        period = query.data.split(":", 1)[1]
        if period not in PERIODS:
            await query.answer("Неизвестный период")
            return
        await send_rating(query, period)
        await query.answer()

    @router.message(Command("mystats"))
    async def cmd_mystats(message: Message) -> None:
        chat_id = message.chat.id
        settings = storage.settings(chat_id)
        user_id = message.from_user.id
        users = {u.user_id: u for u in storage.list_users(chat_id)}
        user = users.get(user_id) or UserRow(user_id, message.from_user.username,
                                             message.from_user.first_name, None)
        count = storage.count_for(chat_id, user_id, None)
        last = storage.last_pick_for(chat_id, user_id)
        await message.answer(mystats_text(user, settings.role_name, count, last))

    return router
```

- [ ] **Step 4: Запустить тесты, убедиться что проходят**

Run: `python -m pytest tests/test_game_format.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add bot/handlers/ tests/test_game_format.py
git commit -m "feat: /rating and /mystats handlers"
```

---

### Task 7: Сервис скачивания видео (downloader)

**Files:**
- Create: `bot/services/downloader.py`
- Create: `tests/test_downloader.py`

**Interfaces:**
- Consumes: ничего.
- Produces:
  - `VideoError(Exception)` — любая ошибка скачивания/обжатия, атрибут `reason: str`.
  - `VideoTooBig(VideoError)` — не влезло после всех ступеней обжатия.
  - `SIZE_LIMIT_BYTES: int` = `48 * 1024 * 1024`.
  - `STAGES: list[dict]` = `[{"scale": 720, "crf": 30}, {"scale": 480, "crf": 33}, {"scale": 360, "crf": 36}]`.
  - `extract_video_url(text: str) -> str | None` — первый URL из текста или `None`.
  - `next_stage_index(size_bytes: int, stage_index: int) -> int | None` — если `size <= SIZE_LIMIT_BYTES` вернуть `None`; иначе индекс следующей ступени или `None`, если ступени кончились (нужно бросить `VideoTooBig`).
  - `class UrlCache(ttl_seconds: int = 600)` — `seen_recently(chat_id: int, url: str, now: datetime) -> bool`, `mark(chat_id: int, url: str, now: datetime) -> None`.
  - `async download_video(url: str, out_dir: Path, cookies: Path | None = None, timeout: float = 300.0) -> Path` — yt-dlp, возвращает путь к MP4.
  - `async compress_video(src: Path, dst: Path, stage: dict) -> Path` — ffmpeg.
  - `async process_video(url: str, workdir: Path, cookies: Path | None = None) -> Path` — скачать и дожимать по ступеням до лимита; чистит промежуточные файлы; не влезло → `VideoTooBig`.

- [ ] **Step 1: Написать падающие тесты**

`tests/test_downloader.py`:
```python
import asyncio
import os
import shutil
import stat
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from bot.services.downloader import (
    SIZE_LIMIT_BYTES, STAGES, UrlCache, VideoTooBig, compress_video,
    download_video, extract_video_url, next_stage_index, process_video,
)

NOW = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize("text,expected", [
    ("смотри https://youtu.be/dQw4w9WgXcQ лол", "https://youtu.be/dQw4w9WgXcQ"),
    ("https://www.youtube.com/watch?v=dQw4w9WgXcQ&si=x", "https://www.youtube.com/watch?v=dQw4w9WgXcQ&si=x"),
    ("тут https://youtube.com/shorts/dQw4w9WgXcQ ок", "https://youtube.com/shorts/dQw4w9WgXcQ"),
    ("реел https://www.instagram.com/reel/ABC123xyz/ да", "https://www.instagram.com/reel/ABC123xyz/"),
    ("пост https://instagram.com/p/ABC123xyz/", "https://instagram.com/p/ABC123xyz/"),
])
def test_extract_video_url_positive(text, expected):
    assert extract_video_url(text) == expected


@pytest.mark.parametrize("text", [
    "просто текст",
    "https://youtube.com/channel/UC123",
    "https://instagram.com/user/",
    "ftp://youtu.be/dQw4w9WgXcQ",
    "https://notyoutube.com/watch?v=dQw4w9WgXcQ",
])
def test_extract_video_url_negative(text):
    assert extract_video_url(text) is None


def test_next_stage_index():
    assert next_stage_index(SIZE_LIMIT_BYTES, 0) is None
    assert next_stage_index(SIZE_LIMIT_BYTES + 1, 0) == 0
    assert next_stage_index(SIZE_LIMIT_BYTES + 1, len(STAGES)) is None


def test_url_cache_ttl():
    cache = UrlCache(ttl_seconds=600)
    cache.mark(1, "https://youtu.be/x", NOW)
    assert cache.seen_recently(1, "https://youtu.be/x", NOW + timedelta(seconds=599))
    assert not cache.seen_recently(1, "https://youtu.be/x", NOW + timedelta(seconds=601))
    assert not cache.seen_recently(2, "https://youtu.be/x", NOW)
    assert not cache.seen_recently(1, "https://youtu.be/y", NOW)


def _make_fake_ytdlp(bin_dir: Path, fixture: Path) -> Path:
    script = bin_dir / "yt-dlp"
    script.write_text(
        "#!/bin/sh\n"
        'while [ "$#" -gt 0 ]; do\n'
        '  if [ "$1" = "-o" ]; then\n'
        f'    cp "{fixture}" "$(dirname "$2")/out.mp4"\n'
        "    exit 0\n"
        "  fi\n"
        "  shift\n"
        "done\n"
        "exit 1\n"
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return script


def test_download_video_with_fake_ytdlp(tmp_path, monkeypatch):
    fixture = tmp_path / "fixture.mp4"
    fixture.write_bytes(b"fake video bytes")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _make_fake_ytdlp(bin_dir, fixture)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")

    out = asyncio.run(download_video("https://youtu.be/x", tmp_path / "out"))
    assert out.read_bytes() == b"fake video bytes"


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
def test_process_video_compresses_oversized(tmp_path, monkeypatch):
    fixture = tmp_path / "fixture.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=duration=2:size=640x480:rate=10",
         "-pix_fmt", "yuv420p", str(fixture)],
        check=True, capture_output=True,
    )
    import bot.services.downloader as downloader_module
    monkeypatch.setattr(downloader_module, "SIZE_LIMIT_BYTES", fixture.stat().st_size - 1)

    out = asyncio.run(process_video("https://youtu.be/x", tmp_path / "work", cookies=None))
    assert out.exists()
    assert out.stat().st_size <= downloader_module.SIZE_LIMIT_BYTES
```

- [ ] **Step 2: Запустить тесты, убедиться что падают**

Run: `python -m pytest tests/test_downloader.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'bot.services.downloader'`

- [ ] **Step 3: Реализовать downloader**

`bot/services/downloader.py`:
```python
import asyncio
import re
from datetime import datetime, timedelta
from pathlib import Path

URL_RE = re.compile(
    r"https?://(?:www\.)?(?:"
    r"youtu\.be/[A-Za-z0-9_\-]{6,}"
    r"|youtube\.com/watch\?[^\s]*v=[A-Za-z0-9_\-]{6,}"
    r"|youtube\.com/shorts/[A-Za-z0-9_\-]{6,}"
    r"|instagram\.com/(?:reel|reels|p)/[A-Za-z0-9_\-.]+"
    r")[^\s]*"
)

SIZE_LIMIT_BYTES = 48 * 1024 * 1024
STAGES = [
    {"scale": 720, "crf": 30},
    {"scale": 480, "crf": 33},
    {"scale": 360, "crf": 36},
]
DOWNLOAD_TIMEOUT = 300.0


class VideoError(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class VideoTooBig(VideoError):
    pass


def extract_video_url(text: str) -> str | None:
    m = URL_RE.search(text)
    return m.group(0) if m else None


def next_stage_index(size_bytes: int, stage_index: int) -> int | None:
    if size_bytes <= SIZE_LIMIT_BYTES:
        return None
    if stage_index >= len(STAGES):
        return None
    return stage_index


class UrlCache:
    def __init__(self, ttl_seconds: int = 600):
        self._ttl = timedelta(seconds=ttl_seconds)
        self._items: dict[tuple[int, str], datetime] = {}

    def seen_recently(self, chat_id: int, url: str, now: datetime) -> bool:
        self._purge(now)
        return (chat_id, url) in self._items

    def mark(self, chat_id: int, url: str, now: datetime) -> None:
        self._purge(now)
        self._items[(chat_id, url)] = now

    def _purge(self, now: datetime) -> None:
        cutoff = now - self._ttl
        self._items = {k: v for k, v in self._items.items() if v > cutoff}


async def _run(cmd: list[str], timeout: float, what: str) -> None:
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout)
    except TimeoutError:
        proc.kill()
        raise VideoError(f"{what}: timeout")
    if proc.returncode != 0:
        tail = (stderr or b"").decode(errors="replace")[-300:]
        raise VideoError(f"{what}: {tail.strip() or 'unknown error'}")


async def download_video(url: str, out_dir: Path,
                         cookies: Path | None = None,
                         timeout: float = DOWNLOAD_TIMEOUT) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    before = set(out_dir.glob("*.mp4"))
    cmd = [
        "yt-dlp",
        "-f", "bv*[height<=720][ext=mp4]+ba[ext=m4a]/b[height<=720]/b",
        "--merge-output-format", "mp4",
        "--no-playlist",
        "-o", str(out_dir / "%(id)s.%(ext)s"),
    ]
    if cookies and Path(cookies).exists():
        cmd += ["--cookies", str(cookies)]
    cmd.append(url)
    await _run(cmd, timeout, "download")
    after = set(out_dir.glob("*.mp4"))
    new = [p for p in after - before]
    if not new:
        candidates = sorted(after, key=lambda p: p.stat().st_mtime)
        if not candidates:
            raise VideoError("download: no output file")
        new = [candidates[-1]]
    return max(new, key=lambda p: p.stat().st_mtime)


async def compress_video(src: Path, dst: Path, stage: dict,
                         timeout: float = 600.0) -> Path:
    dst = Path(dst)
    cmd = [
        "ffmpeg", "-y", "-i", str(src),
        "-vf", f"scale=-2:{stage['scale']}",
        "-c:v", "libx264", "-crf", str(stage["crf"]), "-preset", "fast",
        "-c:a", "aac", "-b:a", "96k",
        "-movflags", "+faststart",
        str(dst),
    ]
    await _run(cmd, timeout, "compress")
    return dst


async def process_video(url: str, workdir: Path,
                        cookies: Path | None = None) -> Path:
    workdir = Path(workdir)
    current = await download_video(url, workdir, cookies)
    try:
        stage_index = 0
        while current.stat().st_size > SIZE_LIMIT_BYTES:
            if stage_index >= len(STAGES):
                raise VideoTooBig("exceeds size limit after all compression stages")
            compressed = await compress_video(
                current, workdir / f"compressed_{stage_index}.mp4", STAGES[stage_index])
            if current != compressed and current.exists():
                current.unlink()
            current = compressed
            stage_index += 1
        return current
    except (VideoTooBig, VideoError):
        for f in workdir.glob("*.mp4"):
            f.unlink(missing_ok=True)
        raise
    except Exception as e:
        for f in workdir.glob("*.mp4"):
            f.unlink(missing_ok=True)
        raise VideoError(str(e)) from e
```

- [ ] **Step 4: Запустить тесты, убедиться что проходят**

Run: `python -m pytest tests/test_downloader.py -v`
Expected: все passed; `test_process_video_compresses_oversized` — skipped, если локально нет ffmpeg (в CI/на VPS с ffmpeg — выполняется)

- [ ] **Step 5: Commit**

```bash
git add bot/services/downloader.py tests/test_downloader.py
git commit -m "feat: video download/compress pipeline (yt-dlp + ffmpeg)"
```

---

### Task 8: Хендлер видео

**Files:**
- Create: `bot/handlers/video.py`
- Create: `tests/test_video_handler.py`

**Interfaces:**
- Consumes: `bot.services.downloader` (Task 7), `bot.storage.Storage`, `bot.personality.Personality`, `bot.config.Config`.
- Produces: `bot.handlers.video.build_video_router(bot, storage: Storage, personality: Personality, config: Config) -> Router` — реагирует только на сообщения, где `extract_video_url` вернул URL. Один обработанный URL на чат одновременно (семафор), глобальный семафор 2, дедупликация через `UrlCache`, «печатает» (`send_chat_action`), в успехе — `send_video` (reply на исходное) с фразой `video_ok`, `VideoError` → `video_fail`, `VideoTooBig` → `video_too_big`. Рабочая директория: `config.data_dir / "tmp" / f"{chat_id}_{message_id}"`, cookies: `config.data_dir / "cookies.txt"` если существует. Плюс чистый хелпер `cleanup_workdirs(data_dir: Path, chat_id: int) -> None` — удаляет `tmp/{chat_id}_*` директории с содержимым (вызывается в `finally` после отправки).

- [ ] **Step 1: Написать тест очистки рабочих директорий**

`tests/test_video_handler.py`:
```python
from pathlib import Path

from bot.handlers.video import cleanup_workdirs


def _make_dir(base: Path, name: str) -> Path:
    d = base / name
    d.mkdir(parents=True)
    (d / "video.mp4").write_bytes(b"x")
    return d


def test_cleanup_removes_only_matching_chat(tmp_path):
    tmp = tmp_path / "data" / "tmp"
    _make_dir(tmp, "1_100")
    _make_dir(tmp, "1_101")
    keep = _make_dir(tmp, "2_100")
    _make_dir(tmp, "1_102")

    cleanup_workdirs(tmp_path / "data", 1)

    remaining = sorted(p.name for p in tmp.iterdir())
    assert remaining == ["2_100"]
    assert (keep / "video.mp4").exists()
```

- [ ] **Step 2: Запустить тест, убедиться что падает**

Run: `python -m pytest tests/test_video_handler.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'bot.handlers.video'`

- [ ] **Step 3: Реализовать хендлер**

`bot/handlers/video.py`:
```python
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
```

- [ ] **Step 4: Запустить тесты, убедиться что проходят**

Run: `python -m pytest tests/test_video_handler.py -v`
Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add bot/handlers/video.py tests/test_video_handler.py
git commit -m "feat: auto video link handler with queue and dedup"
```

---

### Task 9: Сервис мок-ответов (mockery)

**Files:**
- Create: `bot/services/mockery.py`
- Create: `tests/test_mockery.py`

**Interfaces:**
- Consumes: `bot.storage.Settings`.
- Produces:
  - `bot.services.mockery.CONFUSABLES: dict[str, str]` — пары похожих букв (кириллица).
  - `corrupt_text(text: str, rng: random.Random) -> str` — искажение; затрагивает ~15% искажаемых букв (не более 20%), только маппируемые буквы (замена на похожую / удаление / перестановка с соседней), результат ≤ 500 символов.
  - `is_mockable(text: str) -> bool` — `len(text.strip()) >= 10`.
  - `should_mock(settings: Settings, author_id: int, now: datetime, last_mock_at: datetime | None, targets: set[int], rng: random.Random) -> bool` — порядок проверок: `mock_chance == 0` → False; режим `targets` и автор не в `targets` → False; кулдаун не прошёл → False; иначе `rng.random() * 100 < mock_chance`.

- [ ] **Step 1: Написать падающие тесты**

`tests/test_mockery.py`:
```python
import random
from datetime import datetime, timedelta, timezone

from bot.services.mockery import CONFUSABLES, corrupt_text, is_mockable, should_mock
from bot.storage import Settings

NOW = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)
TEXT = "Я эйчар и запрещаю удалёнку и гибрид для всех сотрудников компании"


def test_is_mockable_length():
    assert not is_mockable("коротко")
    assert is_mockable("Я эйчар и запрещаю удалёнку")


def test_corrupt_deterministic_with_seed():
    a = corrupt_text(TEXT, random.Random(42))
    b = corrupt_text(TEXT, random.Random(42))
    assert a == b and a != TEXT


def test_corrupt_only_allowed_operations():
    for seed in range(20):
        out = corrupt_text(TEXT, random.Random(seed))
        allowed = set(TEXT) | set(CONFUSABLES.values())
        assert set(out) <= allowed
        assert len(out) <= 500


def test_corrupt_short_returns_truncated():
    assert corrupt_text("abc", random.Random(1)) == "abc"


def test_should_mock_chance_zero():
    s = Settings(chat_id=1, mock_chance=0)
    assert not should_mock(s, 5, NOW, None, set(), random.Random(1))


def test_should_mock_targets_mode():
    s = Settings(chat_id=1, mock_chance=100, mock_cooldown_min=0, mock_mode="targets")
    assert not should_mock(s, 5, NOW, None, {7}, random.Random(1))
    assert should_mock(s, 7, NOW, None, {7}, random.Random(1))


def test_should_mock_cooldown():
    s = Settings(chat_id=1, mock_chance=100, mock_cooldown_min=10)
    last = NOW - timedelta(minutes=9)
    assert not should_mock(s, 5, NOW, last, set(), random.Random(1))
    assert should_mock(s, 5, NOW, NOW - timedelta(minutes=11), set(), random.Random(1))


def test_should_mock_all_mode_ignores_targets():
    s = Settings(chat_id=1, mock_chance=100, mock_cooldown_min=0)
    assert should_mock(s, 999, NOW, None, set(), random.Random(1))
```

- [ ] **Step 2: Запустить тесты, убедиться что падают**

Run: `python -m pytest tests/test_mockery.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'bot.services.mockery'`

- [ ] **Step 3: Реализовать mockery**

`bot/services/mockery.py`:
```python
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
```

- [ ] **Step 4: Запустить тесты, убедиться что проходят**

Run: `python -m pytest tests/test_mockery.py -v`
Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
git add bot/services/mockery.py tests/test_mockery.py
git commit -m "feat: mock-reply text corruption + trigger logic"
```

---

### Task 10: Хендлер мок-ответов

**Files:**
- Create: `bot/handlers/mock.py`
- Create: `tests/test_mock_router.py`

**Interfaces:**
- Consumes: Task 9 (`is_mockable`, `corrupt_text`, `should_mock`), Task 7 (`extract_video_url`), `bot.storage.Storage`.
- Produces: `bot.handlers.mock.build_mock_router(storage: Storage, personality: Personality, tz_name: str, rng: random.Random | None = None) -> Router` — реагирует на текстовые сообщения без видео-ссылок: если `is_mockable` и `should_mock` → reply искажённым текстом + `set_last_mock`. `personality` принимается для единообразия фабрик (не используется — мок не зависит от характера).

- [ ] **Step 1: Написать тест сборки роутера**

`tests/test_mock_router.py`:
```python
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

from bot.handlers.mock import build_mock_router
from bot.personality import Personality
from bot.db import connect
from bot.storage import Storage

NOW = datetime(2026, 11, 10, 12, 0, tzinfo=timezone(timedelta(hours=3)))


def _build(tmp_path):
    conn = connect(tmp_path / "t.db")
    storage = Storage(conn)
    personality = Personality(Path(__file__).parent.parent / "bot" / "characters",
                              rng=random.Random(1))
    return build_mock_router(storage, personality, "Europe/Moscow", rng=random.Random(1))


def test_router_builds(tmp_path):
    router = _build(tmp_path)
    assert router is not None
```

- [ ] **Step 2: Запустить тест, убедиться что падает**

Run: `python -m pytest tests/test_mock_router.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'bot.handlers.mock'`

- [ ] **Step 3: Реализовать хендлер**

`bot/handlers/mock.py`:
```python
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
```

- [ ] **Step 4: Запустить тесты, убедиться что проходят**

Run: `python -m pytest tests/test_mock_router.py -v`
Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add bot/handlers/mock.py tests/test_mock_router.py
git commit -m "feat: mock-reply message handler"
```

---

### Task 11: Авторизация мини-аппа (initData)

**Files:**
- Create: `bot/webapp/__init__.py` (пустой)
- Create: `bot/webapp/auth.py`
- Create: `tests/test_webapp_auth.py`

**Interfaces:**
- Consumes: `bot.config.Config`.
- Produces: `bot.webapp.auth.AuthError(Exception)`; `validate_init_data(init_data: str, bot_token: str, max_age_seconds: int = 86400) -> dict[str, str]` — проверяет HMAC-SHA256 подпись Telegram и свежесть `auth_date`; при ошибке бросает `AuthError`. Алгоритм Telegram: `secret = HMAC_SHA256(key=b"WebAppData", msg=bot_token)`, `expected = HMAC_SHA256(key=secret, msg=data_check_string).hexdigest()`, где `data_check_string` — пары `k=v` (без `hash`) в алфавитном порядке через `\n`.

- [ ] **Step 1: Написать падающие тесты**

`tests/test_webapp_auth.py`:
```python
import hashlib
import hmac
import time
import urllib.parse

import pytest

from bot.webapp.auth import AuthError, validate_init_data

TOKEN = "123:fake"


def make_init_data(pairs: dict[str, str], token: str = TOKEN) -> str:
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    signature = hmac.new(secret, data_check_string.encode(), hashlib.sha256).hexdigest()
    pairs = dict(pairs, hash=signature)
    return urllib.parse.urlencode(pairs)


def test_valid_init_data():
    pairs = {"query_id": "AA", "user": '{"id":42}', "auth_date": str(int(time.time()))}
    result = validate_init_data(make_init_data(pairs), TOKEN)
    assert result["query_id"] == "AA"
    assert "hash" not in result


def test_tampered_data_raises():
    pairs = {"query_id": "AA", "auth_date": str(int(time.time()))}
    good = make_init_data(pairs)
    tampered = good.replace("AA", "BB")
    with pytest.raises(AuthError):
        validate_init_data(tampered, TOKEN)


def test_wrong_token_raises():
    pairs = {"auth_date": str(int(time.time()))}
    with pytest.raises(AuthError):
        validate_init_data(make_init_data(pairs), "999:other")


def test_expired_raises():
    pairs = {"auth_date": str(int(time.time()) - 90000)}
    with pytest.raises(AuthError, match="expired"):
        validate_init_data(make_init_data(pairs), TOKEN)


def test_missing_hash_raises():
    with pytest.raises(AuthError):
        validate_init_data("auth_date=123", TOKEN)
```

- [ ] **Step 2: Запустить тесты, убедиться что падают**

Run: `python -m pytest tests/test_webapp_auth.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'bot.webapp.auth'`

- [ ] **Step 3: Реализовать auth**

`bot/webapp/__init__.py`: пустой файл.

`bot/webapp/auth.py`:
```python
import hashlib
import hmac
import time
import urllib.parse


class AuthError(Exception):
    pass


def validate_init_data(init_data: str, bot_token: str,
                       max_age_seconds: int = 86400) -> dict[str, str]:
    pairs = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
    received = pairs.pop("hash", None)
    if not received:
        raise AuthError("no hash")
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received):
        raise AuthError("bad hash")
    auth_date = int(pairs.get("auth_date", "0") or 0)
    if int(time.time()) - auth_date > max_age_seconds:
        raise AuthError("expired")
    return pairs
```

- [ ] **Step 4: Запустить тесты, убедиться что проходят**

Run: `python -m pytest tests/test_webapp_auth.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add bot/webapp/__init__.py bot/webapp/auth.py tests/test_webapp_auth.py
git commit -m "feat: telegram webapp initdata validation"
```

---

### Task 12: API админки (FastAPI)

**Files:**
- Create: `bot/webapp/app.py`
- Create: `bot/webapp/static/.gitkeep` (пустой, статику добавим в Task 13)
- Create: `tests/test_webapp_api.py`

**Interfaces:**
- Consumes: Task 2 (`Storage`, `Settings`), Task 3 (`Personality`), Task 4 (`rating.format_top`, `PERIODS`), Task 11 (`AuthError`, `validate_init_data`), `bot.config.Config`.
- Produces: `bot.webapp.app.create_app(bot, storage: Storage, personality: Personality, config: Config) -> FastAPI`:
  - Заголовок `X-Telegram-Init-Data` → `validate_init_data` → `user` JSON → `user_id`; доступ разрешён если `user_id == config.superadmin_id` или `await bot.get_chat_member(config.chat_id, user_id)` вернул статус `creator`/`administrator`. Иначе 401/403.
  - `GET /api/state` → `{"settings": {...}, "rating_top": [...], "known_users": [...], "mock_targets": [...]}`. `known_users` — до 200 пользователей из `list_users` (id, display_name, username).
  - `POST /api/character {character}`, `POST /api/role {role_name}`, `POST /api/pick_time {pick_time}`, `POST /api/auto_pick {enabled}`, `POST /api/exclude_last {enabled}`, `POST /api/mock {mock_chance, mock_cooldown_min, mock_mode}`, `POST /api/mock_targets {user_ids}` — каждый применяется через `storage.update_settings(chat_id, ...)` / `replace_mock_targets` и возвращает обновлённый `settings`; `ValueError` → 422.
  - `POST /api/reset_rating` — `clear_picks(config.chat_id)`.
  - Все операции по чату `config.chat_id`.

- [ ] **Step 1: Написать падающие тесты**

`tests/test_webapp_api.py`:
```python
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
```

- [ ] **Step 2: Запустить тесты, убедиться что падают**

Run: `python -m pytest tests/test_webapp_api.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'bot.webapp.app'`

- [ ] **Step 3: Реализовать app.py**

`bot/webapp/app.py`:
```python
import json
from dataclasses import asdict
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from bot.config import Config
from bot.personality import Personality
from bot.services.rating import format_top
from bot.storage import Storage
from bot.webapp.auth import AuthError, validate_init_data

MAX_KNOWN_USERS = 200


class CharacterPayload(BaseModel):
    character: str


class RolePayload(BaseModel):
    role_name: str = Field(min_length=1, max_length=64)


class PickTimePayload(BaseModel):
    pick_time: str


class EnabledPayload(BaseModel):
    enabled: bool


class MockPayload(BaseModel):
    mock_chance: int = Field(ge=0, le=100)
    mock_cooldown_min: int = Field(ge=0)
    mock_mode: str


class MockTargetsPayload(BaseModel):
    user_ids: list[int]


def create_app(bot, storage: Storage, personality: Personality,
               config: Config) -> FastAPI:
    app = FastAPI(title="tg-bot admin")

    async def require_admin(request: Request) -> int:
        init_data = request.headers.get("X-Telegram-Init-Data", "")
        try:
            pairs = validate_init_data(init_data, config.bot_token)
        except AuthError:
            raise HTTPException(401, "invalid init data")
        user = json.loads(pairs.get("user", "{}"))
        user_id = int(user.get("id", 0))
        if user_id == config.superadmin_id:
            return user_id
        if config.chat_id is None:
            raise HTTPException(403, "no chat configured")
        try:
            member = await bot.get_chat_member(config.chat_id, user_id)
        except Exception:
            raise HTTPException(403, "admin check failed")
        if member.status not in {"creator", "administrator"}:
            raise HTTPException(403, "not an admin")
        return user_id

    def current_settings():
        return storage.settings(config.chat_id)

    def ok(settings):
        return {"settings": asdict(settings)}

    @app.get("/api/state")
    async def state(_: int = Depends(require_admin)):
        s = current_settings()
        users = storage.list_users(config.chat_id)[:MAX_KNOWN_USERS]
        top_rows = [(u, c) for uid, c in storage.top(config.chat_id, None)
                    for u in users if u.user_id == uid]
        return {
            "settings": asdict(s),
            "rating_top": format_top(top_rows, "all", s.role_name) if top_rows else "",
            "known_users": [
                {"user_id": u.user_id, "display_name": u.display_name,
                 "username": u.username} for u in users
            ],
            "mock_targets": sorted(storage.mock_targets(config.chat_id)),
        }

    @app.post("/api/character")
    async def character(payload: CharacterPayload, _: int = Depends(require_admin)):
        return _update(character=payload.character)

    @app.post("/api/role")
    async def role(payload: RolePayload, _: int = Depends(require_admin)):
        return _update(role_name=payload.role_name.strip())

    @app.post("/api/pick_time")
    async def pick_time(payload: PickTimePayload, _: int = Depends(require_admin)):
        return _update(pick_time=payload.pick_time)

    @app.post("/api/auto_pick")
    async def auto_pick(payload: EnabledPayload, _: int = Depends(require_admin)):
        return _update(auto_pick_enabled=payload.enabled)

    @app.post("/api/exclude_last")
    async def exclude_last(payload: EnabledPayload, _: int = Depends(require_admin)):
        return _update(exclude_last=payload.enabled)

    @app.post("/api/mock")
    async def mock(payload: MockPayload, _: int = Depends(require_admin)):
        return _update(mock_chance=payload.mock_chance,
                       mock_cooldown_min=payload.mock_cooldown_min,
                       mock_mode=payload.mock_mode)

    @app.post("/api/mock_targets")
    async def mock_targets(payload: MockTargetsPayload, _: int = Depends(require_admin)):
        storage.replace_mock_targets(config.chat_id, payload.user_ids)
        return ok(current_settings())

    @app.post("/api/reset_rating")
    async def reset_rating(_: int = Depends(require_admin)):
        storage.clear_picks(config.chat_id)
        return {"ok": True}

    def _update(**fields):
        try:
            settings = storage.update_settings(config.chat_id, **fields)
        except ValueError as e:
            raise HTTPException(422, str(e))
        return ok(settings)

    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        from fastapi.staticfiles import StaticFiles
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

    return app
```

- [ ] **Step 4: Запустить тесты, убедиться что проходят**

Run: `python -m pytest tests/test_webapp_api.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add bot/webapp/app.py bot/webapp/static/.gitkeep tests/test_webapp_api.py
git commit -m "feat: admin webapp api (fastapi)"
```

---

### Task 13: Фронтенд мини-аппа

**Files:**
- Create: `bot/webapp/static/index.html`
- Create: `bot/webapp/static/app.js`
- Create: `bot/webapp/static/style.css`
- Test: `tests/test_static_served.py`

**Interfaces:**
- Consumes: Task 12 API (эндпоинты и форматы из его Produces).
- Produces: статика, доступная на `/`. Фронт читает `window.Telegram.WebApp.initData` и шлёт её заголовком `X-Telegram-Init-Data`; вызывает ровно те эндпоинты, что описаны в Task 12.

- [ ] **Step 1: Написать падающий тест раздачи статики**

`tests/test_static_served.py`:
```python
import random
from pathlib import Path

from fastapi.testclient import TestClient

from bot.config import Config
from bot.db import connect
from bot.personality import Personality
from bot.storage import Storage
from bot.webapp.app import create_app


def test_static_index_served(tmp_path):
    conn = connect(tmp_path / "t.db")
    storage = Storage(conn)
    personality = Personality(Path(__file__).parent.parent / "bot" / "characters",
                              rng=random.Random(1))
    config = Config(bot_token="123:fake", superadmin_id=7,
                    webapp_domain="x.example.com", chat_id=-1,
                    data_dir=tmp_path, timezone="Europe/Moscow")
    client = TestClient(create_app(object(), storage, personality, config))
    r = client.get("/")
    assert r.status_code == 200
    assert "tg-bot admin" in r.text
```

- [ ] **Step 2: Запустить тест, убедиться что падает**

Run: `python -m pytest tests/test_static_served.py -v`
Expected: FAIL — нет `index.html` → 404

- [ ] **Step 3: Создать статику**

`bot/webapp/static/index.html`:
```html
<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>tg-bot admin</title>
  <link rel="stylesheet" href="/style.css">
  <script src="https://telegram.org/js/telegram-web-app.js"></script>
</head>
<body>
  <main>
    <h1>Админка бота</h1>

    <section>
      <h2>Характер</h2>
      <div class="row">
        <button id="char-clean" class="pill">Цензурный</button>
        <button id="char-adult" class="pill">18+</button>
      </div>
    </section>

    <section>
      <h2>Игра</h2>
      <label>Название роли <input id="role" type="text" maxlength="64"></label>
      <label>Время выбора <input id="pick_time" type="time"></label>
      <label class="check"><input id="auto_pick" type="checkbox"> Автовыбор каждый день</label>
      <label class="check"><input id="exclude_last" type="checkbox"> Не выбирать вчерашнего</label>
    </section>

    <section>
      <h2>Мок-ответы</h2>
      <label>Вероятность, % <input id="mock_chance" type="number" min="0" max="100"></label>
      <label>Кулдаун, мин <input id="mock_cooldown" type="number" min="0"></label>
      <label>Режим
        <select id="mock_mode">
          <option value="all">На всех</option>
          <option value="targets">Только на выбранных</option>
        </select>
      </label>
      <div id="targets_block" hidden>
        <input id="targets_search" type="search" placeholder="Поиск…">
        <div id="targets_list"></div>
      </div>
    </section>

    <section>
      <h2>Рейтинг</h2>
      <pre id="rating"></pre>
    </section>

    <section>
      <button id="save" class="primary">Сохранить</button>
      <button id="reset_rating" class="danger">Сбросить рейтинг</button>
    </section>

    <p id="status"></p>
  </main>
  <script src="/app.js"></script>
</body>
</html>
```

`bot/webapp/static/app.js`:
```javascript
const tg = window.Telegram.WebApp;
tg.expand();

const $ = (id) => document.getElementById(id);
const status = (msg) => { $("status").textContent = msg; };

async function api(path, options = {}) {
  const res = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-Telegram-Init-Data": tg.initData,
      ...(options.headers || {}),
    },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status}: ${text}`);
  }
  return res.json();
}

let state = null;

function fill(state) {
  const s = state.settings;
  $("role").value = s.role_name;
  $("pick_time").value = s.pick_time;
  $("auto_pick").checked = s.auto_pick_enabled;
  $("exclude_last").checked = s.exclude_last;
  $("mock_chance").value = s.mock_chance;
  $("mock_cooldown").value = s.mock_cooldown_min;
  $("mock_mode").value = s.mock_mode;
  $("char-clean").classList.toggle("active", s.character === "clean");
  $("char-adult").classList.toggle("active", s.character === "adult");
  $("rating").textContent = state.rating_top || "Пока пусто";
  renderTargets(state);
  $("targets_block").hidden = s.mock_mode !== "targets";
}

function selectedTargets() {
  return [...document.querySelectorAll("#targets_list input:checked")]
    .map((cb) => Number(cb.value));
}

function renderTargets(state) {
  const chosen = new Set(state.mock_targets);
  const filter = $("targets_search").value.toLowerCase();
  const list = $("targets_list");
  list.innerHTML = "";
  for (const u of state.known_users) {
    const name = (u.display_name + (u.username ? " @" + u.username : "")).toLowerCase();
    if (filter && !name.includes(filter)) continue;
    const label = document.createElement("label");
    label.className = "check";
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.value = u.user_id;
    cb.checked = chosen.has(u.user_id);
    label.append(cb, " " + u.display_name + (u.username ? " (@" + u.username + ")" : ""));
    list.append(label);
  }
}

async function load() {
  state = await api("/api/state");
  fill(state);
}

async function save() {
  await api("/api/role", { method: "POST", body: JSON.stringify({ role_name: $("role").value }) });
  await api("/api/pick_time", { method: "POST", body: JSON.stringify({ pick_time: $("pick_time").value }) });
  await api("/api/auto_pick", { method: "POST", body: JSON.stringify({ enabled: $("auto_pick").checked }) });
  await api("/api/exclude_last", { method: "POST", body: JSON.stringify({ enabled: $("exclude_last").checked }) });
  await api("/api/mock", {
    method: "POST",
    body: JSON.stringify({
      mock_chance: Number($("mock_chance").value),
      mock_cooldown_min: Number($("mock_cooldown").value),
      mock_mode: $("mock_mode").value,
    }),
  });
  if ($("mock_mode").value === "targets") {
    await api("/api/mock_targets", { method: "POST", body: JSON.stringify({ user_ids: selectedTargets() }) });
  }
  status("Сохранено");
  await load();
}

async function setCharacter(character) {
  await api("/api/character", { method: "POST", body: JSON.stringify({ character }) });
  status("Характер: " + character);
  await load();
}

$("save").onclick = () => save().catch((e) => status("Ошибка: " + e.message));
$("char-clean").onclick = () => setCharacter("clean").catch((e) => status("Ошибка: " + e.message));
$("char-adult").onclick = () => setCharacter("adult").catch((e) => status("Ошибка: " + e.message));
$("mock_mode").onchange = () => { $("targets_block").hidden = $("mock_mode").value !== "targets"; };
$("targets_search").oninput = () => renderTargets(state);
$("reset_rating").onclick = async () => {
  if (!confirm("Сбросить весь рейтинг? Это не отменить.")) return;
  await api("/api/reset_rating", { method: "POST" });
  status("Рейтинг сброшен");
  await load();
};

load().catch((e) => status("Ошибка загрузки: " + e.message));
```

`bot/webapp/static/style.css`:
```css
:root { color-scheme: dark; }
body { font-family: system-ui, sans-serif; background: #14161a; color: #e8e8e8; margin: 0; }
main { max-width: 480px; margin: 0 auto; padding: 16px; display: flex; flex-direction: column; gap: 16px; }
h1 { font-size: 20px; margin: 8px 0 0; }
h2 { font-size: 15px; margin: 0 0 8px; color: #9aa4b2; }
section { background: #1d2026; border-radius: 12px; padding: 14px; display: flex; flex-direction: column; gap: 10px; }
label { display: flex; flex-direction: column; gap: 4px; font-size: 14px; }
label.check { flex-direction: row; align-items: center; gap: 8px; }
input, select { background: #14161a; border: 1px solid #333; border-radius: 8px; color: inherit; padding: 8px; font-size: 14px; }
.row { display: flex; gap: 8px; }
.pill { flex: 1; padding: 10px; border-radius: 10px; border: 1px solid #333; background: #14161a; color: inherit; }
.pill.active { background: #2b5cff; border-color: #2b5cff; }
.primary { padding: 12px; border-radius: 10px; border: 0; background: #2b5cff; color: #fff; font-size: 15px; }
.danger { padding: 12px; border-radius: 10px; border: 0; background: #b3261e; color: #fff; font-size: 15px; }
#targets_list { max-height: 220px; overflow: auto; display: flex; flex-direction: column; gap: 6px; }
pre { white-space: pre-wrap; margin: 0; font-size: 13px; }
#status { min-height: 18px; color: #9aa4b2; font-size: 13px; }
```

- [ ] **Step 4: Запустить тесты, убедиться что проходят**

Run: `python -m pytest tests/test_static_served.py -v`
Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add bot/webapp/static/ tests/test_static_served.py
git commit -m "feat: admin mini app frontend"
```

---

### Task 14: Админ-команды (/character, /admin) и permissions

**Files:**
- Create: `bot/services/permissions.py`
- Create: `bot/handlers/admin.py`
- Create: `tests/test_permissions.py`

**Interfaces:**
- Consumes: `bot.config.Config`.
- Produces:
  - `bot.services.permissions.is_admin(bot, chat_id: int, user_id: int, superadmin_id: int | None) -> bool` — True если `user_id == superadmin_id` либо статус `creator`/`administrator`; при ошибке API — False.
  - `bot.handlers.admin.build_admin_router(bot, storage: Storage, personality: Personality, config: Config) -> Router` — `/character`: inline-кнопки `char:clean` / `char:adult`, переключают настройку чата (только админы, иначе фраза `error`); `/admin`: сообщение с inline-кнопкой WebApp на `config.webapp_url`; `/start`, `/help`: фраза `help`.

- [ ] **Step 1: Написать падающие тесты**

`tests/test_permissions.py`:
```python
import asyncio

import pytest

from bot.services.permissions import is_admin


class Member:
    def __init__(self, status):
        self.status = status


class Bot:
    def __init__(self, status):
        self.status = status

    async def get_chat_member(self, chat_id, user_id):
        if self.status == "raise":
            raise RuntimeError("telegram error")
        return Member(self.status)


def test_superadmin_always_admin():
    assert asyncio.run(is_admin(Bot("member"), 1, 7, 7)) is True


def test_admin_status():
    assert asyncio.run(is_admin(Bot("administrator"), 1, 42, 7)) is True
    assert asyncio.run(is_admin(Bot("creator"), 1, 42, 7)) is True


def test_member_not_admin():
    assert asyncio.run(is_admin(Bot("member"), 1, 42, 7)) is False


def test_api_error_is_not_admin():
    assert asyncio.run(is_admin(Bot("raise"), 1, 42, 7)) is False


def test_no_superadmin_configured():
    assert asyncio.run(is_admin(Bot("member"), 1, 42, None)) is False
```

- [ ] **Step 2: Запустить тесты, убедиться что падают**

Run: `python -m pytest tests/test_permissions.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'bot.services.permissions'`

- [ ] **Step 3: Реализовать permissions и хендлеры**

`bot/services/permissions.py`:
```python
async def is_admin(bot, chat_id: int, user_id: int,
                   superadmin_id: int | None) -> bool:
    if superadmin_id is not None and user_id == superadmin_id:
        return True
    try:
        member = await bot.get_chat_member(chat_id, user_id)
    except Exception:
        return False
    return member.status in {"creator", "administrator"}
```

`bot/handlers/admin.py`:
```python
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import (CallbackQuery, InlineKeyboardButton,
                           InlineKeyboardMarkup, Message, WebAppInfo)

from bot.config import Config
from bot.personality import Personality
from bot.services.permissions import is_admin
from bot.storage import Storage


def _char_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Цензурный", callback_data="char:clean"),
        InlineKeyboardButton(text="18+", callback_data="char:adult"),
    ]])


def build_admin_router(bot, storage: Storage, personality: Personality,
                       config: Config) -> Router:
    router = Router()

    async def admin_only(message: Message) -> bool:
        return await is_admin(bot, message.chat.id, message.from_user.id,
                              config.superadmin_id)

    @router.message(Command("start", "help"))
    async def cmd_help(message: Message) -> None:
        settings = storage.settings(message.chat.id)
        await message.answer(personality.phrase(settings.character, "help"))

    @router.message(Command("character"))
    async def cmd_character(message: Message) -> None:
        settings = storage.settings(message.chat.id)
        if not await admin_only(message):
            await message.answer(personality.phrase(settings.character, "error"))
            return
        await message.answer("Характер бота:", reply_markup=_char_kb())

    @router.callback_query(F.data.startswith("char:"))
    async def cb_character(query: CallbackQuery) -> None:
        character = query.data.split(":", 1)[1]
        chat_id = query.message.chat.id
        user_id = query.from_user.id
        if not await is_admin(bot, chat_id, user_id, config.superadmin_id):
            await query.answer("Только для админов", show_alert=True)
            return
        try:
            storage.update_settings(chat_id, character=character)
        except ValueError:
            await query.answer("Неизвестный характер", show_alert=True)
            return
        await query.answer("Характер: " + character)

    @router.message(Command("admin"))
    async def cmd_admin(message: Message) -> None:
        settings = storage.settings(message.chat.id)
        if not await admin_only(message):
            await message.answer(personality.phrase(settings.character, "error"))
            return
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="Открыть админку",
                                 web_app=WebAppInfo(url=config.webapp_url)),
        ]])
        await message.answer("Админка:", reply_markup=kb)

    return router
```

- [ ] **Step 4: Запустить тесты, убедиться что проходят**

Run: `python -m pytest tests/test_permissions.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add bot/services/permissions.py bot/handlers/admin.py tests/test_permissions.py
git commit -m "feat: admin commands + permissions check"
```

---

### Task 15: Точка входа (wiring)

**Files:**
- Create: `bot/__main__.py`
- Create: `tests/test_entrypoint.py`

**Interfaces:**
- Consumes: все предыдущие задачи.
- Produces: `bot.__main__.create_dispatcher(config: Config, storage: Storage, personality: Personality, bot) -> aiogram.Dispatcher` — регистрирует роутеры (game, video, mock, admin) и message-middleware, пишущую каждого автора в `users`; `main()` — config → logging → storage → personality → bot → dispatcher → одновременно `dp.start_polling(bot)`, uvicorn (`0.0.0.0:8080`) и `run_scheduler`; глобальный error handler логирует исключения апдейтов.

- [ ] **Step 1: Написать падающий тест сборки диспетчера**

`tests/test_entrypoint.py`:
```python
import random
from pathlib import Path

from aiogram import Bot

from bot.__main__ import create_dispatcher
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
```

- [ ] **Step 2: Запустить тест, убедиться что падает**

Run: `python -m pytest tests/test_entrypoint.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'bot.__main__'` (или ошибка импорта при запуске модуля)

- [ ] **Step 3: Реализовать __main__.py**

`bot/__main__.py`:
```python
import asyncio
import logging
import random
from datetime import datetime
from pathlib import Path

import uvicorn
from aiogram import Bot, Dispatcher
from aiogram.types import Message

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
    async def on_error(event, exception):
        log.exception("update failed: %s", exception)

    return dp


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
    for f in tmp.glob("**/*"):
        f.unlink(missing_ok=True)

    log.info("starting bot (polling) + webapp (:8080)")
    await asyncio.gather(
        dp.start_polling(bot),
        server.serve(),
        run_scheduler(bot, storage, personality, config.timezone),
    )


if __name__ == "__main__":
    asyncio.run(amain())
```

- [ ] **Step 4: Запустить тесты, убедиться что проходят**

Run: `python -m pytest tests/test_entrypoint.py -v`
Expected: 1 passed

- [ ] **Step 5: Прогнать весь тест-сьют и commit**

Run: `python -m pytest tests -q`
Expected: все зелёные

```bash
git add bot/__main__.py tests/test_entrypoint.py
git commit -m "feat: bot entrypoint (polling + webapp + scheduler)"
```

---

### Task 16: Docker, compose, README

**Files:**
- Create: `Dockerfile`
- Create: `.dockerignore`
- Create: `docker-compose.yml`
- Create: `docker-compose.dev.yml`
- Create: `Caddyfile`
- Modify: `README.md` (создать)
- Modify: `.env.example` (дополнить комментариями)

**Interfaces:**
- Consumes: весь код предыдущих задач.
- Produces: собираемый образ и поднимаемый стек; инструкция по деплою.

- [ ] **Step 1: Файлы образа и стека**

`Dockerfile`:
```dockerfile
FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot ./bot

ENV TZ=Europe/Moscow \
    DATA_DIR=/app/data
VOLUME ["/app/data"]

CMD ["python", "-m", "bot"]
```

`.dockerignore`:
```
.git
.venv
venv
__pycache__
*.pyc
.env
data
tests
docs
*.md
!README.md
```

`docker-compose.yml`:
```yaml
services:
  bot:
    build: .
    env_file: .env
    volumes:
      - bot-data:/app/data
    restart: unless-stopped

  caddy:
    image: caddy:2
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy-data:/data
      - caddy-config:/config
    environment:
      WEBAPP_DOMAIN: ${WEBAPP_DOMAIN}

  watchtower:
    image: containrrr/watchtower
    profiles: ["watchtower"]
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    command: --interval 3600 --cleanup

volumes:
  bot-data:
  caddy-data:
  caddy-config:
```

`docker-compose.dev.yml`:
```yaml
services:
  bot:
    ports:
      - "8080:8080"
```

`Caddyfile`:
```
{$WEBAPP_DOMAIN} {
    reverse_proxy bot:8080
}
```

`.env.example` (дополнить комментарии):
```text
# Токен от @BotFather (обязательно)
BOT_TOKEN=
# Твой numeric user id — полный доступ к админке (узнать: @userinfobot)
SUPERADMIN_ID=
# ID группы (отрицательное число, узнать: добавить @getmyid_bot в группу)
CHAT_ID=
# Домен мини-аппа, например admin.example.com
WEBAPP_DOMAIN=
TZ=Europe/Moscow
```

- [ ] **Step 2: README.md**

````markdown
# tg-bot

Telegram-бот для группы: игра «Олег дня», мок-ответы, скачивание YouTube/Instagram видео, мини-апп админка.

## Локальный запуск

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env   # заполнить BOT_TOKEN и т.д.
python -m bot
```

Мини-апп локально: `docker compose -f docker-compose.yml -f docker-compose.dev.yml up` и туннель на порт 8080.

## Деплой на VPS

1. DNS: запись A домена `WEBAPP_DOMAIN` → IP VPS.
2. `git clone`, `cp .env.example .env`, заполнить `BOT_TOKEN`, `SUPERADMIN_ID`, `CHAT_ID`, `WEBAPP_DOMAIN`.
3. `docker compose up -d` (опционально `--profile watchtower` для автообновлений).
4. @BotFather: `/setprivacy` → Disable (бот должен видеть все сообщения для ловли ссылок и мок-ответов); Bot Settings → Menu Button → URL `https://<WEBAPP_DOMAIN>`.
5. Добавить бота в группу, выдать права админа (необязательно, но рекомендуется).

## Instagram

Для приватного/возрастного контента положить `cookies.txt` (экспорт из браузера, Netscape-формат) в data-volume: `docker cp cookies.txt tg-bot-bot-1:/app/data/cookies.txt`.

## Тесты

```bash
python -m pytest tests -q
```

## Ручной чек-лист (тестовая группа)

- [ ] `/rating`, `/mystats` — отвечают, пустой рейтинг → заглушка
- [ ] Автовыбор в заданное время (или временно поставить время «через минуту»)
- [ ] Ссылка YouTube (watch, shorts, youtu.be) → видео в чате
- [ ] Ссылка Instagram reel → видео в чате
- [ ] Мок-ответ на сообщение (поставить `mock_chance=100`)
- [ ] Режим targets: реагирует только на выбранных
- [ ] `/character`, `/admin` — только для админов
- [ ] Мини-апп: сохранение настроек, сброс рейтинга
````

- [ ] **Step 3: Валидация**

Run: `python -m pytest tests -q`
Expected: все зелёные

Run: `docker compose config`
Expected: вывод конфигурации без ошибок (требуется docker; если локально недоступен — пропустить, выполнить на VPS)

Run: `docker build -t tg-bot .`
Expected: успешная сборка (если docker недоступен — выполнить на VPS при деплое)

- [ ] **Step 4: Commit**

```bash
git add Dockerfile .dockerignore docker-compose.yml docker-compose.dev.yml Caddyfile README.md .env.example
git commit -m "chore: docker build, compose stack, readme"
```

---

## Self-Review (заполнено автором плана)

**Spec coverage:**
- Игра «Олег дня» (автовыбор, рейтинг, /mystats, сброс) → Tasks 2, 4, 5, 6, 12 ✔
- Характеры (2 шт., переключение /character + мини-апп) → Tasks 3, 14, 12 ✔
- Видео (фильтр, yt-dlp, ffmpeg ступени, 48 МБ, очередь, дедупликация, cookies) → Tasks 7, 8, 16 (README) ✔
- Мок-ответы (вероятность, кулдаун, режим targets, список целей, ≤500 симв.) → Tasks 2, 9, 10, 12 ✔
- Админка мини-апп (initData HMAC, админ-чек, все эндпоинты, фронт) → Tasks 11, 12, 13 ✔
- Docker compose + Caddy + README → Task 16 ✔
- Ограничения/деплой/privacy mode → Task 16 README ✔

**Placeholder scan:** TBD/TODO/«аналогично» отсутствуют; каждый код-степ содержит полный код. ✔

**Type consistency:** `Storage`/`Settings`/`UserRow` (Task 2) используются с теми же именами в Tasks 4, 5, 6, 9, 10, 12; `extract_video_url` (Task 7) — в Tasks 8, 10; `validate_init_data` (Task 11) — в Task 12; `PERIODS`/`format_top` (Task 4) — в Tasks 6, 12; `process_video` (Task 7) — в Task 8; `cleanup_workdirs` (Task 8) — внутри Task 8 и при старте в Task 15. Имена фабрик роутеров согласованы с Task 15. ✔

**Известные допущения:** `CHAT_ID` добавлен как env (в спеке отсутствовал, но необходим для админ-чека мини-аппа); `last_pick_for` добавлен в Storage для честного `/mystats` (дата последнего звания конкретного пользователя); статика мини-аппа монтируется в `create_app` после регистрации API-роутов, чтобы `Mount("/")` не перехватывал `/api/*`; в Dockerfile копируется только `bot/` (тесты в образ не попадают).
