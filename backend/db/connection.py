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


def init_db() -> None:
    """Создаёт таблицы если их нет. Вызывается при старте приложения."""
    schema = _SCHEMA_FILE.read_text(encoding="utf-8")
    with get_db() as db:
        db.executescript(schema)


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
