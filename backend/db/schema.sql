-- schema.sql — SQLite схема ContentHub
--
-- ContentHub хранит только то, чего нет в других проектах:
--   - пользователей и сессии (мультиюзер)
--   - audit log действий через UI
--   - кэш метрик (обновляется фоновой задачей)
--   - cross-project линковку видео → PreLend

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ─────────────────────────────────────────────────────────────────────────────
-- Пользователи
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    username        TEXT UNIQUE NOT NULL,
    password_hash   TEXT NOT NULL,          -- bcrypt
    role            TEXT NOT NULL DEFAULT 'viewer',  -- 'admin' | 'operator' | 'viewer'
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    last_login      TEXT
);

-- Дефолтный admin (пароль устанавливается при первом запуске)
INSERT OR IGNORE INTO users (username, password_hash, role)
VALUES ('admin', '__CHANGE_ME__', 'admin');

-- ─────────────────────────────────────────────────────────────────────────────
-- JWT refresh-токены / сессии
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS sessions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash  TEXT NOT NULL,      -- SHA-256 от refresh token
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token_hash);
CREATE INDEX IF NOT EXISTS idx_sessions_user  ON sessions(user_id, expires_at);

-- ─────────────────────────────────────────────────────────────────────────────
-- Audit log всех действий через UI
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT NOT NULL DEFAULT (datetime('now')),
    user_id     INTEGER REFERENCES users(id),
    username    TEXT,               -- денормализовано для читаемости
    action      TEXT NOT NULL,      -- 'config_write' | 'patch_approve' | 'agent_stop' | ...
    project     TEXT,               -- 'ShortsProject' | 'PreLend' | 'Orchestrator'
    detail_json TEXT                -- JSON с деталями: что изменено, старое/новое значение
);

CREATE INDEX IF NOT EXISTS idx_audit_log_ts      ON audit_log(ts DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_project ON audit_log(project, ts DESC);

-- ─────────────────────────────────────────────────────────────────────────────
-- Кэш метрик (обновляется фоновой asyncio-задачей каждые 60 сек)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS metrics_cache (
    key         TEXT PRIMARY KEY,   -- 'dashboard' | 'funnel_7d' | 'funnel_30d' | 'agents'
    value_json  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

-- ─────────────────────────────────────────────────────────────────────────────
-- Cross-project линковка: SP видео → PreLend sub_id
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS video_funnel_links (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    sp_stem         TEXT NOT NULL,          -- ключ из analytics.json (имя видео без расширения)
    platform        TEXT NOT NULL,          -- 'youtube' | 'tiktok' | 'instagram'
    video_url       TEXT,                   -- URL опубликованного видео
    prelend_sub_id  TEXT,                   -- значение sub_id, переданное в PreLend
    linked_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_funnel_links_stem ON video_funnel_links(sp_stem);
CREATE INDEX IF NOT EXISTS idx_funnel_links_sub  ON video_funnel_links(prelend_sub_id);
