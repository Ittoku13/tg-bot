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
