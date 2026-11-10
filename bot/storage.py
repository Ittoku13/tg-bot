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
