-- 2026-04-13_agent_events_registry.sql
-- Выравнивает структуру agent_events в ContentHub.
--
-- ВАЖНО:
-- Для существующих БД применяйте idempotent-скрипт:
--   python scripts/migrate_contenthub_db.py --db /path/to/contenthub.db
--
-- SQL-файл хранится как audit trail миграции.

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
);

CREATE INDEX IF NOT EXISTS idx_agent_events_created
    ON agent_events(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_events_hook
    ON agent_events(hook_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_events_experiment
    ON agent_events(experiment_id, created_at DESC);
