"""
db/connection.py — подключение к SQLite ContentHub.

Паттерн:
    with get_db() as db:
        db.execute(...)
        db.commit()
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

import config as cfg

_SCHEMA_FILE = Path(__file__).parent / "schema.sql"


def _migrate_agent_events_registry(conn: sqlite3.Connection) -> None:
    """Гарантирует актуальную структуру agent_events в contenthub.db."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_events (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            source_project  TEXT NOT NULL,
            agent_name      TEXT NOT NULL,
            event_type      TEXT NOT NULL,
            severity        TEXT NOT NULL DEFAULT 'info',
            creative_id     TEXT,
            hook_type       TEXT,
            experiment_id   TEXT,
            agent_run_id    TEXT,
            payload_json    TEXT NOT NULL DEFAULT '{}',
            created_at      TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )

    rows = conn.execute("PRAGMA table_info(agent_events)").fetchall()
    cols = {r[1] for r in rows}
    if "source_project" not in cols:
        conn.execute("ALTER TABLE agent_events ADD COLUMN source_project TEXT")
    if "agent_name" not in cols:
        conn.execute("ALTER TABLE agent_events ADD COLUMN agent_name TEXT")
    if "event_type" not in cols:
        conn.execute("ALTER TABLE agent_events ADD COLUMN event_type TEXT")
    if "severity" not in cols:
        conn.execute("ALTER TABLE agent_events ADD COLUMN severity TEXT DEFAULT 'info'")
    if "creative_id" not in cols:
        conn.execute("ALTER TABLE agent_events ADD COLUMN creative_id TEXT")
    if "hook_type" not in cols:
        conn.execute("ALTER TABLE agent_events ADD COLUMN hook_type TEXT")
    if "experiment_id" not in cols:
        conn.execute("ALTER TABLE agent_events ADD COLUMN experiment_id TEXT")
    if "agent_run_id" not in cols:
        conn.execute("ALTER TABLE agent_events ADD COLUMN agent_run_id TEXT")
    if "payload_json" not in cols:
        conn.execute("ALTER TABLE agent_events ADD COLUMN payload_json TEXT DEFAULT '{}'")
    if "created_at" not in cols:
        conn.execute("ALTER TABLE agent_events ADD COLUMN created_at TEXT DEFAULT (datetime('now'))")

    conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_events_created ON agent_events(created_at DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_events_hook ON agent_events(hook_type, created_at DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_events_experiment ON agent_events(experiment_id, created_at DESC)")


def init_db() -> None:
    """Создаёт таблицы если их нет. Вызывается при старте приложения."""
    schema = _SCHEMA_FILE.read_text(encoding="utf-8")
    with get_db() as db:
        db.executescript(schema)
        _migrate_agent_events_registry(db)


@contextmanager
def get_db():
    """Контекстный менеджер: возвращает sqlite3.Connection с настройками."""
    conn = sqlite3.connect(str(cfg.CONTENTHUB_DB), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()
