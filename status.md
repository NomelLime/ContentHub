# ContentHub — status.md
> Не пушить в гит. Выдавать в чате при старте каждой сессии.

---

## РОЛЬ
Единая веб-панель управления для всех проектов (ShortsProject, PreLend, Orchestrator).
Заменяет ручную правку конфигов, файлов и запуск агентов через CLI.

---

## СТЕК

| Слой        | Технология                                               |
|-------------|----------------------------------------------------------|
| Backend     | Python 3.11+, FastAPI, Uvicorn                           |
| БД          | SQLite (`data/contenthub.db`)                            |
| Auth        | JWT (python-jose) + bcrypt                               |
| WebSocket   | FastAPI WebSocket + asyncio broadcaster                  |
| Frontend    | React 18 + Vite + TypeScript + Tailwind CSS              |
| HTTP Client | fetch API (lib/api.ts)                                   |

---

## Сессия 24 (31.03.2026) — Native metrics UI + KPI colors + Orchestrator expanded metrics

| Область | Изменение |
|---------|-----------|
| **Dashboard backend (`services/metrics_collector.py`)** | Подтянуты расширенные метрики из `Orchestrator`: `decision_metrics`, `node_duration_sec`, `agent_metrics` (включая SP agent health и PL traffic heartbeat), а также блок `sp.platform_native_metrics` из `ShortsProject/data/analytics.json`. |
| **Dashboard UI (`pages/DashboardPage.tsx`)** | Добавлены карточки KPI качества решений (apply/success/rollback/patch), operational блоки цикла (duration/commands/pipeline/supply), top-3 native metrics, и цветовая индикация `green/yellow/red` по порогам. |
| **Новая страница (`pages/PlatformNativeMetricsPage.tsx`)** | Таблица `recent_20` native metrics с фильтрами по платформе/аккаунту и сортировкой (`views/likes/comments/engagement/uploaded_at`, asc/desc). |
| **Навигация (`App.tsx`)** | Добавлен маршрут и пункт меню: `/platform-native-metrics` → **Native Metrics**. |

**Тесты/проверки:**
- `python -m pytest backend/tests/test_analytics.py -q` — ✅
- Lints по изменённым фронтенд/бэкенд файлам — ✅

---

## СТРУКТУРА ПРОЕКТА

```
ContentHub/
├── backend/
│   ├── main.py                        # FastAPI entrypoint, CORS, роутинг, WS
│   ├── config.py                      # Пути ко всем проектам (SP, PL, ORC)
│   ├── requirements.txt
│   ├── .env.example
│   ├── db/
│   │   ├── connection.py              # get_db() context manager, init_db()
│   │   └── schema.sql                 # 5 таблиц: users, sessions, audit_log, metrics_cache, video_funnel_links
│   ├── api/
│   │   ├── routes/
│   │   │   ├── auth.py                # POST /api/auth/login, /logout, /me, /refresh (с token rotation)
│   │   │   ├── dashboard.py           # GET /api/dashboard
│   │   │   ├── agents.py              # GET /api/agents, POST /api/agents/{name}/start|stop
│   │   │   ├── patches.py             # GET/POST /api/patches/{id}/approve|reject (409 при race)
│   │   │   ├── configs.py             # GET/PUT /api/configs/* + /history (git log/show/revert)
│   │   │   ├── advertisers.py         # CRUD + GET /compare (метрики по офферам)
│   │   │   ├── analytics.py           # GET /api/analytics/*, /audit (admin), /pl, /plan-quality
│   │   │   ├── system.py              # GET /api/system/health
│   │   │   ├── events.py              # POST /api/events (JWT operator или X-Internal-Events-Key)
│   │   │   └── ws_route.py            # WebSocket /ws (JWT auth через ?token=)
│   │   └── ws/
│   │       └── broadcaster.py         # asyncio broadcast loop с diff-логикой
│   ├── services/
│   │   ├── auth.py                    # JWT create/verify, bcrypt, RBAC depends
│   │   ├── metrics_collector.py       # Агрегация метрик; PreLend + geo_breakdown из /metrics
│   │   ├── config_reader.py           # Чтение конфигов (SP, PreLend, Orchestrator)
│   │   ├── config_writer.py           # Запись конфигов, git history/revert, approve/reject патчей
│   │   ├── health_checker.py          # Агрегированный health SP / PL API / ORC
│   │   └── agent_controller.py        # Запись флагов в agent_memory.json
│   ├── integrations/
│   │   └── prelend_client.py          # Шим → Orchestrator/integrations/prelend_client
│   └── tests/
│       ├── conftest.py                # Изолированная БД, фикстуры admin/viewer
│       ├── test_auth.py               # login, rate-limit, RBAC, logout, refresh
│       ├── test_patches.py            # list, approve (viewer→403), nonexistent→409
│       ├── test_token_rotation.py     # Token rotation: replay protection, role в ответе
│       ├── test_health_checker.py     # /api/system/health
│       └── test_advertiser_buttons.py # advertisers API smoke
└── frontend/
    └── src/
        ├── lib/
        │   └── api.ts                 # + configs.history*, advertisers.compare, analytics.audit
        ├── hooks/
        │   └── useWebSocket.ts        # WS хук: getAccessToken() при каждом коннекте
        ├── components/
        │   ├── ConfigHistory/         # git log / просмотр / откат конфигов
        │   ├── AdvertiserCompare/   # таблица сравнения офферов и метрик
        │   └── Dashboard/SystemHealth.tsx
        ├── pages/
        │   ├── LoginPage.tsx          # auth.login() → setAccessToken(at, role) in-memory
        │   ├── DashboardPage.tsx      # getUserRole() [FIX#3], SystemHealth
        │   ├── PatchesPage.tsx        # getUserRole() + DiffViewer [FIX#3]
        │   ├── ConfigPage.tsx         # SP + рекламодатели + compare + история конфигов
        │   ├── AnalyticsPage.tsx      # FunnelChart + PlGeoTable (PreLend по ГЕО)
        │   ├── AuditPage.tsx          # audit_log (admin)
        │   ├── OperatorCommandsPage.tsx
        │   └── UsersPage.tsx          # CRUD пользователей
        └── App.tsx                    # RequireAuth, /audit (admin), адаптивный layout
```

---

## ХРАНЕНИЕ ТОКЕНОВ (актуальное состояние)

| Данные        | Хранилище     | Описание |
|---------------|---------------|----------|
| access_token  | JS memory     | Теряется при F5 → авто-refresh через cookie |
| refresh_token | httpOnly cookie | JS не видит. Path=/api/auth. Token rotation при каждом /refresh [FIX#6] |
| role          | JS memory     | getUserRole() / setUserRole(). Восстанавливается из /refresh ответа [FIX#3] |

**Поток после F5:**
```
RequireAuth → initAuth() → POST /api/auth/refresh
    → setAccessToken(at) + setUserRole(role)
    → новый refresh cookie (token rotation)
    → рендер страницы с актуальной role
```

---

## РОЛИ ПОЛЬЗОВАТЕЛЕЙ

| Роль | Доступ |
|------|--------|
| `admin` | Всё, включая пользователей (`/api/auth/users`), страницу **Аудит** (`GET /api/analytics/audit`) |
| `operator` | Запись конфигов, approve/reject патчей, splits, агенты; `POST /api/events` (JWT или внутренний ключ) |
| `viewer` | Только чтение: dashboard, аналитика, агенты, патчи |

---

## ENV (.env.example + монорепа)

**В git (источник правды по секретам):** **`GitHub/secrets.enc.env`** (SOPS) + **`.sops.yaml`** (публичные ключи age). Приватный ключ только локально/VPS: **`age/age.key`**, переменная **`SOPS_AGE_KEY_FILE`**. Рабочий plaintext для правок: **`secrets.plain.env`** → `scripts/sops-encrypt.*` → коммит **`secrets.enc.env`**. Подробно: **`SECRETS-SOPS.md`**, скрипты **`scripts/sops-*.ps1`** / **`sops-run-contenthub.*`**.

**Порядок загрузки в процессе (backend/main.py):** сначала **`GitHub/.secrets.env`** (если файл есть — типично после `sops-decrypt` или старый dev), затем **`backend/.env`** (переопределения). Если секреты уже в **`os.environ`** (например **`sops exec-env secrets.enc.env -- uvicorn …`**), `load_dotenv` не подменяет их (`override=False` для общего файла). Тот же приоритет `.secrets.env` → локальный `.env` у Orchestrator (`config.py`), ShortsProject (`pipeline/config.py`), PreLend Internal API (`internal_api/config.py`).

**PreLend на VPS (SOPS):** расшифровка в **`/run/prelend.env`**, systemd **`EnvironmentFile`** для php-fpm и **`prelend-internal-api`**; отдельного **`GitHub/.secrets.env`** на сервере нет. См. **`PreLend/deploy/vps_one_command.sh`**.

Шаблон имён переменных (не коммитить значения): **`GitHub/.secrets.env.example`**, **`GitHub/secrets.plain.env.example`**.

```env
# JWT
CONTENTHUB_SECRET_KEY=your-secret-key-here   # python3 -c "import secrets; print(secrets.token_hex(32))"
ACCESS_TOKEN_EXPIRE_MIN=60
REFRESH_TOKEN_EXPIRE_DAYS=30

# Внутренние события (POST /api/events с заголовком X-Internal-Events-Key)
CONTENTHUB_INTERNAL_EVENTS_KEY=

# Пути к проектам
GITHUB_ROOT=/path/to/projects    # Обязательно — иначе EnvironmentError при старте

# Web-сервер
CONTENTHUB_HOST=0.0.0.0
CONTENTHUB_PORT=8000

# CORS: задать конкретные origin, НЕ "*" (несовместимо с allow_credentials=True)
# По умолчанию в config.py уже включены 5173/3000/4173 и 127.0.0.1 — при необходимости переопредели:
# ALLOWED_ORIGINS=http://localhost:5173,http://localhost:4173

# Cookie secure (false для localhost, true для HTTPS)
COOKIE_SECURE=false

# PreLend Internal API (VPS → SSH tunnel → localhost:9090)
PL_INTERNAL_API_URL=http://localhost:9090
PL_INTERNAL_API_KEY=   # тот же ключ, что PL_INTERNAL_API_KEY на VPS (internal_api)
# Dev: если туннеля нет, но правишь локальный PreLend/config/settings.json:
# CONTENTHUB_PL_SETTINGS_TRUST_LOCAL_FALLBACK=1
# Устаревание RUNNING в панели агентов SP (минуты):
# SP_AGENT_STATUS_STALE_MINUTES=25

# JSON-логи (опционально)
# LOG_FORMAT=json
```

---

## СТАТУС РАЗРАБОТКИ

**Дата создания:** 15.03.2026
**Фаза:** Backend + Frontend реализованы. Все code review исправления применены. Следующий шаг: деплой.

[x] Этап 1 — Backend FastAPI
[x] Этап 2 — Frontend React + Vite
[x] Этап 3 — Интеграция с PreLend Internal API
[x] Этап 4 (partial) — Все критические фиксы безопасности применены
[x] Этап 5 — Тесты API endpoints (conftest, test_auth, test_patches, test_token_rotation)
[ ] Деплой + первый запуск (uvicorn backend.main:app --port 8000)

---

## ИСТОРИЯ СЕССИЙ

### Сессия 1 (15.03.2026) — Полная реализация

Создан новый проект с нуля. Backend FastAPI, SQLite, JWT, WebSocket, Frontend React+Vite+TS+Tailwind.

### Сессия 2 (16.03.2026) — Рефакторинг PreLend → Internal API

PreLend теперь на VPS. Все операции через HTTP к Internal API (порт 9090).

### Сессия 3 (18.03.2026) — Безопасность перед боевым запуском

| Файл | Исправление |
|------|-------------|
| `backend/config.py` | Авто-генерация SECRET_KEY если не задан; флаг `_is_temp_secret`; WARNING в лог |
| `backend/main.py` | Проверка `_is_temp_secret` в lifespan |
| `backend/api/routes/ws_route.py` | JWT проверка через `?token=<JWT>` до `accept()`. Код `4001` при отказе |
| `frontend/src/hooks/useWebSocket.ts` | `getAccessToken()` из памяти; при `code=4001` нет авторекконекта |
| `backend/api/routes/configs.py` | Pydantic модели `PLAlertsUpdate` + `PLSettingsUpdate` с числовыми границами |
| `backend/api/routes/auth.py` | Rate limiter: 5 попыток за 60 сек, 429 при превышении |
| `backend/config.py` | Хардкод GITHUB_ROOT → EnvironmentError если не задан |

### Сессия 4 (18.03.2026) — Перенос refresh_token из localStorage в httpOnly cookie

| Файл | Исправление |
|------|-------------|
| `backend/api/routes/auth.py` | refresh_token → httpOnly cookie (path=/api/auth). `refresh()` читает из Cookie |
| `backend/config.py` | + `COOKIE_SECURE` |
| `frontend/src/lib/api.ts` | accessToken → module variable. `initAuth()` → refresh при F5 |
| `frontend/src/App.tsx` | `RequireAuth` с async `initAuth()` + loading spinner |

### Сессия 5 (18.03.2026) — FEAT-C: diff-viewer + FEAT-D: plan quality

| Файл | Исправление |
|------|-------------|
| `backend/api/routes/patches.py` | + `GET /api/patches/{id}/diff` |
| `frontend/src/pages/PatchesPage.tsx` | built-in side-by-side DiffViewer, PatchCard с Approve/Reject |
| `backend/api/routes/analytics.py` | + `GET /api/analytics/plan-quality?limit=N` |

### Code Review (18.03.2026) — Сессия 11: полное применение всех фиксов

Применены все исправления из полного code review 4 проектов (v2 от 18.03.2026).

**ContentHub:**

| # | Severity | Файл(ы) | Исправление |
|---|----------|---------|-------------|
| FIX#3 | Critical | `api.ts`, `App.tsx`, `DashboardPage.tsx`, `PatchesPage.tsx`, `ConfigPage.tsx`, `LoginPage.tsx` | `role` из `localStorage` → in-memory `_userRole`. Добавлены `getUserRole()` / `setUserRole()`. После F5: role восстанавливается из /refresh ответа. `canControl` на дашборде работает корректно |
| FIX#6 | High | `backend/api/routes/auth.py` | Token rotation при `/refresh`: DELETE старой сессии → INSERT новой → новый cookie. Replay attack защита |
| FIX#7 | High | `backend/main.py` | В `metrics_refresh_loop()` раз в ~1ч: `DELETE FROM sessions WHERE expires_at < now()`. Предотвращает неограниченный рост таблицы sessions |
| FIX#8 | High | `backend/tests/test_token_rotation.py` (NEW) | 4 теста: rotation меняет cookie, старый token → 401, role в ответе, logout → refresh → 401 |
| FIX#9 | Medium | `backend/api/routes/auth.py` | Pydantic `TokenResponse`, `UserInfo`, `SuccessResponse`; `response_model` на всех endpoints |
| FIX#16 | Medium | `backend/main.py` | CORS: `allow_methods=["GET","POST","PUT","DELETE","OPTIONS"]`, `allow_headers=["Authorization","Content-Type"]`. Warning при `"*"` в ALLOWED_ORIGINS |

**PreLend:**

| # | Severity | Файл(ы) | Исправление |
|---|----------|---------|-------------|
| FIX#1 | Critical | `src/BotFilter.php` | `DC_SUBNETS` (prefix /8 блоки) → `DC_CIDRS` с `ip2long()`. 90 точных диапазонов. Lazy-init `getDcRanges()` |
| FIX#4 | High | `public/postback.php` | `HTTP_X_FORWARDED_FOR` (подделываемый) → `HTTP_CF_CONNECTING_IP` через `ClickLogger::getRealIp()` |
| FIX#5 | High | `internal_api/auth.py` | Warning при dev-режиме (однократно за процесс); инструкция в `.env.example` |
| FIX#10 | Medium | `data/init_db.sql` | `idx_conv_rate_limit ON conversions(advertiser_id, source, created_at)` |
| FIX#13 | Medium | `src/BotFilter.php`, `public/index.php`, тесты | Полная миграция на `FilterResult` enum. Старые `const` BC-совместимы |
| FIX#17 | Medium | `src/TemplateRenderer.php` | Fallback-ветка отсутствующего шаблона: `http_response_code(200)` → `http_response_code(404)` |

**Orchestrator:**

| # | Severity | Файл(ы) | Исправление |
|---|----------|---------|-------------|
| FIX#2 | Critical | `modules/evolution.py` | Санитизация: `agent_statuses`, `shave_suspects`, `strategist_recs` через `_san()`. Публичный `sanitize_for_prompt()` в `code_evolver.py` |
| FIX#11 | Medium | `main_orchestrator.py` | `_cleanup_old_data()`: metrics_snapshots >90d, notifications >30d, планы >180d — раз в сутки |
| FIX#14 | Medium | `modules/evolution.py` | `quality_block`: тернарный оператор → читаемый `if`-chain |
| FIX#15 | Medium | `db/patches.py` | `datetime('now')` SQLite → `datetime.now(timezone.utc).isoformat()` во всех `mark_patch_*()` |

**ShortsProject:**

| # | Severity | Файл(ы) | Исправление |
|---|----------|---------|-------------|
| FIX#18 | Low | `pipeline/session_manager.py` | `datetime.now()` → `datetime.now(timezone.utc)` в `mark_session_verified()` и `get_session_age_hours()`. Нормализация старых naive-записей |

**Cross-project (ContentHub + Orchestrator):**

| # | Severity | Файл(ы) | Исправление |
|---|----------|---------|-------------|
| FIX#9 | High | `backend/services/config_writer.py`, `backend/api/routes/patches.py` | `rowcount=0` → warning; endpoint → 409 Conflict при race condition |
| FIX#12 | Medium | `backend/api/routes/auth.py` | Pydantic response_model для всех endpoints |

---

## ЧЕКЛИСТ ПОСЛЕ ВСЕХ ИСПРАВЛЕНИЙ

- [x] `grep -rn "localStorage" ContentHub/frontend/src/` — нет реальных вызовов (только комментарии)
- [x] `backend/tests/test_token_rotation.py` — 4 теста token rotation
- [x] `python -m pytest backend/tests/ -q` — юнит-тесты (без живого PreLend)
- [ ] `PL_INTERNAL_API_INTEGRATION=1 python -m pytest tests/test_prelend_internal_api_live.py -v` — проверка туннеля :9090 и ключа
- [ ] Smoke: login → dashboard → кнопки start/stop видны admin
- [ ] Smoke: login → F5 → role сохранился (in-memory через /refresh)
- [ ] Smoke: `curl localhost:8000/health` → ok
- [ ] Smoke: `curl localhost:9090/health` → ok
- [ ] PreLend: `php tests/test_bot_filter.php` — зелёные (DC_CIDRS + новые тесты)
- [ ] `.env.example` — без рабочих ключей (только инструкции по генерации)

### Code Review v2 (18.03.2026) — дополнительные исправления после верификации тестов

| # | Severity | Файл(ы) | Исправление |
|---|----------|---------|-------------|
| BUG-F | High | `backend/tests/conftest.py` | `_login_failures` — глобальный `defaultdict` в `auth.py`, не сбрасывался между тестами. `TestLogin::test_login_rate_limit` делал 5 неудач для `testadmin` → все следующие тесты получали 429. Добавлен `@pytest.fixture(autouse=True) reset_rate_limiter()` с `.clear()` до и после каждого теста |
| BUG-G | Low | `backend/tests/test_patches.py` | `test_diff_endpoint_exists` ожидал `404`, но без `ORC_DB` endpoint корректно возвращает `503 Service Unavailable`. Исправлено: `assert resp.status_code in (404, 503)` |

**Финальный статус тестов:**
- `python -m pytest backend/tests/ -q` → **23/23** ✅
- `grep -rn "localStorage" frontend/src/` → 0 реальных вызовов ✅

**Коммиты Code Review v2:**

| Коммит | Файл(ы) | Суть |
|--------|---------|------|
| `bb14558` | 10 файлов | FIX#3 role in-memory, FIX#6 token rotation, FIX#7 sessions cleanup, FIX#9 response_model, FIX#16 CORS |
| `ee5ceaa` | conftest.py, test_patches.py | reset_rate_limiter fixture, diff 503 |

---

### Сессия 6 (21.03.2026) — Инцидент деплоя на новой машине (Windows) и восстановление

**Симптомы:**
- `Error loading ASGI app. Could not import module "main"` при запуске из корня `ContentHub/`.
- `module 'config' has no attribute 'DB_PATH'` при старте lifespan.
- `OSError: Задайте GITHUB_ROOT ...` несмотря на наличие `.env`.
- `HTTP 403` от `http://localhost:9090/agents` и `/metrics` (Invalid or missing API key).
- После очистки debug-кода: `NameError: _agent_log is not defined`.

**Корневые причины:**
1. Неверная точка запуска (`uvicorn main:app` из `ContentHub/`, а не из `ContentHub/backend`).
2. Конфликт импортов из-за порядка `sys.path`: подхватывался `Orchestrator/db/connection.py` вместо `ContentHub/backend/db/connection.py`.
3. `.env` читался не жёстко из `backend/.env`; плюс в одном из прогонов `GITHUB_ROOT` был закомментирован.
4. Несовпадение/неподхват `PL_INTERNAL_API_KEY` между ContentHub и PreLend Internal API (systemd env на VPS).
5. Человеческая ошибка при ручной очистке instrumentation (оставшийся вызов `_agent_log`).

**Исправлено в коде ContentHub:**
- `backend/config.py`:
  - `load_dotenv(dotenv_path=BASE_DIR / ".env")` — жёсткая загрузка env из `backend`.
  - fallback для `GITHUB_ROOT`: если не задан, берётся родительская директория при наличии `ShortsProject/PreLend/Orchestrator`.
  - путь `Orchestrator` добавляется в `sys.path` через `append`, чтобы не перехватывать `backend/db`.
- Удалена временная debug-instrumentation и остаточные вызовы `_agent_log`.

**Рантайм-верификация (финал):**
- `uvicorn main:app --port 8000` из `ContentHub/backend` — старт успешный.
- `GET /health` -> `200 OK`.
- БД инициализируется: лог `БД инициализирована`.

**Операционные команды (актуальные):**
```bash
# Windows (из backend):
cd C:\Users\MSI-Vector16\Documents\GitHub\ContentHub\backend
uvicorn main:app --port 8000

# Альтернатива запуску из корня ContentHub:
uvicorn backend.main:app --port 8000
```

**Создание/обновление admin (one-liner, Windows CMD):**
```bash
cd C:\Users\MSI-Vector16\Documents\GitHub\ContentHub\backend && python -c "import sqlite3, config as cfg; from services.auth import hash_password; conn=sqlite3.connect(str(cfg.CONTENTHUB_DB)); conn.execute(\"INSERT OR REPLACE INTO users (username, password_hash, role) VALUES (?, ?, ?)\", (\"admin\", hash_password(\"1234567\"), \"admin\")); conn.commit(); print(\"admin upserted\"); conn.close()"
```

**Проверка admin (one-liner):**
```bash
cd C:\Users\MSI-Vector16\Documents\GitHub\ContentHub\backend && python -c "import sqlite3, config as cfg; conn=sqlite3.connect(str(cfg.CONTENTHUB_DB)); conn.row_factory=sqlite3.Row; row=conn.execute(\"SELECT username, role FROM users WHERE username=?\", (\"admin\",)).fetchone(); print(dict(row) if row else \"admin not found\"); conn.close()"
```

### Сессия 7 (21.03.2026) — Стабилизация UI, сборки и unified launcher

**Что исправлено (кратко):**
- FE fixed: падение `frontend` из-за отсутствующего экспорта `advertisers` в `api.ts`.
- FE/API contract sync: добавлены методы `auth.users.*`, `configs.getSP/updateSP`, `analytics.funnel`.
- BE auth API extended: добавлены endpoints `POST /api/auth/users`, `PUT /api/auth/users/{id}/role`; `GET /api/auth/users` возвращает `last_login`.
- UI fixed: вкладки `Пользователи`, `Патчи`, `Аналитика`, `Конфиги` снова работают.
- TS build fixed: устранены ошибки `TS2339/TS2322` (`auth.users`, `MetricCard color`, `AlertFeed props`), `npm run build` зелёный.
- Agent UX: в `AgentPanel` добавлена кнопка `?` с кратким описанием каждого агента.

**Локальный запуск в один файл (Windows):**
- Добавлены:
  - `run-all.ps1` — единый оркестратор (build + backend + frontend preview + tunnel).
  - `run-all.cmd` — обёртка запуска.
  - `run-all.shareable.cmd` — переносимый шаблон для git.
  - `run-all.local.cmd` — локальный private launcher (в ignore).
- Launcher переведён в режим **одного окна** (`-NoNewWindow`), с авто-остановкой дочерних процессов по `Ctrl+C`.
- Добавлены health-check после старта:
  - `Backend /health`
  - `Frontend root`
- Логи запуска: `ContentHub/.runtime/*.log`.

**Git / ignore housekeeping:**
- `run-all.local.cmd` исключён из отслеживания (через `.gitignore` + `git rm --cached`).
- Усилен игнор Python cache:
  - `backend/api/routes/__pycache__/`
  - `backend/api/routes/__pycache__/*.pyc`

**Текущий рабочий сценарий запуска:**
```bash
# One-click
run-all.local.cmd

# Проверка
http://localhost:4173
http://localhost:8000/health
```

### Сессия 8 (22.03.2026) — Аналитика PreLend по ГЕО в UI

| Файл | Изменение |
|------|-----------|
| `PreLend/internal_api/routes/metrics.py` | `GET /metrics` → поле **`geo_breakdown`** (массив по ISO-2: clicks, conversions, cr). |
| `backend/services/metrics_collector.py` | `_collect_pl_summary(period_hours=…)` прокидывает `geo_breakdown` и `period_hours`. |
| `backend/api/routes/analytics.py` | `GET /api/analytics/pl?period_hours=1..168`. |
| `frontend/src/lib/api.ts` | `analytics.pl(periodHours)`. |
| `frontend/src/components/PlGeoTable/PlGeoTable.tsx` (NEW) | Таблица со сортировкой по колонкам; период 24ч / 72ч / 7д. |
| `frontend/src/pages/AnalyticsPage.tsx` | Подключён `PlGeoTable` над блоком воронки. |

**Зависимость:** на VPS после обновления PreLend с `geo_breakdown` — **`systemctl restart prelend-internal-api`**, иначе ответ `/metrics` без нового поля.

### Сессия 9 (27.03.2026) — PreLend рекламодатели в UI, шаблоны, совместимость с Internal API

| Область | Изменение |
|---------|-----------|
| `frontend/src/lib/api.ts` | Исправлены пути: рекламодатели → `GET/POST/PUT/DELETE /api/advertisers` (раньше несуществующий `/configs/PreLend/advertisers`). Добавлены `advertisers.create`, `advertisers.templates`. |
| `frontend/src/components/AdvertiserManager/AdvertiserManager.tsx` | Форма **нового** рекламодателя (поля как в API); **редактирование** существующего с полным набором полей; выпадающие списки шаблонов; блок **Шаблон клоаки** (`cloak_template`) + сохранение; генератор **HMAC secret**. |
| `backend/api/routes/advertisers.py` | `GET /api/advertisers/templates`; при ошибке сохранения различаются 404 «не найден» и 500 «Internal API не подтвердил». |
| `backend/services/config_reader.py` | `read_pl_templates()` + **fallback**: если Internal API не отдаёт `/templates`, список шаблонов читается с диска `PreLend/templates/{offers,cloaked}`. |
| `backend/services/config_writer.py` | Fallback локальная запись `PL_SETTINGS` / `PL_ADVERTISERS` при сбое PUT; проверка согласованности с Internal API; правки `write_pl_advertiser`. |
| `backend/tests/test_advertiser_buttons.py` (NEW) | Smoke-тесты кнопок/эквивалентов API (`templates`, `cloak`, CRUD). |
| **Сборка** | После изменений фронта: `npm run build` (обновление `dist` для `vite preview`). |
| **Тесты** | `pytest backend/tests/ -q` → **26 passed** (включая новые). |

**Эксплуатация:** на VPS нужны актуальный PreLend Internal API и права на **`config/`** + **`data/`**; **`PL_INTERNAL_API_KEY`** совпадает с общим секретом (**`GitHub/.secrets.env`**) и с окружением **`prelend-internal-api`** на сервере (**`/run/prelend.env`** или unit). Если при сохранении рекламодателей в UI приходит **HTTP 500** и в тексте ошибки есть **`Permission denied`** и путь **`.../config/tmp`** — на VPS у **`www-data`** нет записи в **`/var/www/prelend/config/`**: пошаговое исправление и профилактика описаны в **`PreLend/status.md`** → раздел **«ОБЯЗАТЕЛЬНО: права на каталог config/»** (и сессия **25** в том же файле).

### Сессия 10 (27.03.2026) — Телеметрия Orchestrator на дашборде, вкладка команд оператора

| Область | Изменение |
|---------|-----------|
| **`backend/config.py`** | **`ORC_POLICY_TRACE`** — путь к `Orchestrator/data/policy_command_trace.jsonl`. |
| **`backend/api/routes/operator_commands.py`** (NEW) | **`GET /api/operator-commands/trace?limit=…`** (1–5000) — последние записи JSONL; авторизация `require_viewer`. |
| **`backend/main.py`** | Подключён роутер `operator_commands`. |
| **`frontend/src/pages/DashboardPage.tsx`** | Блок Orchestrator: отображение **`cycle_outcome`**, JSON **`cycle_summary`**, строка **`node_outcomes`** (если есть в `orchestrator_telemetry.json`). |
| **`frontend/src/pages/OperatorCommandsPage.tsx`** (NEW) | Вкладка **«Команды ОР»**: список событий из трейса команд (лимит 200–5000, обновление). |
| **`frontend/src/App.tsx`** | Маршрут `/operator-commands`, пункт навигации. |
| **`frontend/src/lib/api.ts`** | **`operatorCommands.trace(limit)`**. |

Данные для дашборда по-прежнему приходят из `metrics_collector` → кэш `metrics_cache` (поля телеметрии расширены на стороне Orchestrator).

### Сессия 11 (28.03.2026) — Вход, превью, агенты SP, PreLend settings, туннель

**Симптомы:** HTTP 500 при логине с `vite preview` (:4173); «RUNNING» у EDITOR при мёртвом процессе; HTTP 500 при сохранении шаблона клоаки / настройки PreLend; падение `run-all` из‑за `plink` (пароль).

| Область | Изменение |
|---------|-----------|
| **`frontend/vite.config.ts`** | Прокси `/api` и `/ws` продублированы в **`preview`** (раньше только `server`). Без этого запросы с `:4173` не доходили до FastAPI → 500/ошибки на `/auth/login`. |
| **`backend/config.py`** | Дефолт **`ALLOWED_ORIGINS`**: `localhost`/`127.0.0.1` для портов **5173, 3000, 4173** (CORS при обращении к backend с другого origin). |
| **`backend/services/auth.py`** | **`verify_password`**: `try/except` вокруг `bcrypt.checkpw` — битый хеш в SQLite не даёт необработанный 500. |
| **`frontend/.../AgentPanel.tsx`** | Статус вида **`RUNNING: …`** для цвета и кнопок разбирается по первому токену до **`:`** (совпадает с форматом в `agent_memory.json`). |
| **`backend/services/agent_controller.py`** | Устаревшие **`RUNNING`/`WAITING`**: по **`kv.agent_status_updated_at`** и fallback на mtime файла; порог **`SP_AGENT_STATUS_STALE_MINUTES`** (дефолт 25). В ответе — **`UNKNOWN`** + пояснение в `detail`. |
| **`ShortsProject/pipeline/agent_memory.py`** | **`set_agent_status`** пишет **`kv.agent_status_updated_at[AGENT]`** и вызывает **`_save()`** — снимок на диске соответствует последнему статусу. |
| **`backend/services/config_writer.py`** | **`write_pl_settings`**: явные **`RuntimeError`** при пустом GET после fallback, список расходящихся полей; опция **`CONTENTHUB_PL_SETTINGS_TRUST_LOCAL_FALLBACK=1`** пропускает сверку с API (только dev). |
| **`backend/config.py`** | Флаг **`PL_SETTINGS_TRUST_LOCAL_FALLBACK`** из env. |
| **`backend/api/routes/configs.py`** | **`RuntimeError`** из `write_pl_settings` → **HTTP 502** с `detail` (вместо голого 500). |
| **`run-all.ps1`** | При выходе туннеля в исключение подмешиваются последние строки **`tunnel.err.log`**. |
| **PreLend** `internal_api/routes/configs.py` | Whitelist **`settings`**: добавлены **`test_conversion_day`**, **`postback_token`** — иначе полный PUT из ContentHub мог получать **400** на VPS. |

**Операционно (кратко):**
- Туннель: `ssh -N -L 9090:127.0.0.1:9090 user@vps` (или `plink` из `run-all.local.cmd`); **`PL_INTERNAL_API_KEY`** совпадает в **`ContentHub/backend/.env`** и в окружении Internal API на VPS (**`systemd` + `/run/prelend.env`** при SOPS или явный **`Environment=`** в unit).
- Перезапуск Internal API на VPS: **`sudo systemctl restart prelend-internal-api`**.
- Тесты ContentHub после правок: **`pytest backend/tests/ -q`** → **30 passed** (актуально на момент сессии).

**Чеклист (обновить вручную при деплое):**
- [x] Логин с `http://localhost:4173` после `npm run build` + `npm run preview`
- [x] Сохранение **`cloak_template`** при живом туннеле и совпадающем API-ключе (или `CONTENTHUB_PL_SETTINGS_TRUST_LOCAL_FALLBACK=1` только для локального JSON)
- [ ] На VPS: задеплоен актуальный **`internal_api/routes/configs.py`** (whitelist), сервис перезапущен

### Сессия 12 (28.03.2026) — План 10–14 (частичная реализация в репозитории)

Реализовано по `development_plan_sessions_10_14.md`:

| Область | Изменение |
|---------|-----------|
| **ContentHub** | `GET /api/system/health` + `services/health_checker.py`, виджет **`SystemHealth`**, сетка метрик `grid-cols-1 sm:lg`, таблица **`system_events`**, **`POST /api/events`**, broadcaster шлёт **`system_event`** по WS, тесты **`test_health_checker.py`**. |
| **PreLend** | Таблицы **`shave_cache`**, **`click_fingerprints`**, **`video_links`** в **`data/init_db.sql`**; Router читает shave из кэша; **`cron/recalc_shave.py`**, **`cron/retry_postbacks.py`**; Internal API **`POST /metrics/recalc-shave`**, **`POST /register_video`**; дедуп в **`index.php`**; **`GeoAdapter`** + **`GeoDetector`/`ClickLogger`**; postback → **`postback_retry.jsonl`**; тесты **`test_click_dedup.php`**. |
| **ShortsProject** | **`pipeline/pipeline_state.py`**, **`run_pipeline.py`** (`--only`, `--resume`, чекпоинты), **`PRELEND_*`** + вызов **`register_video`** из **`uploader.py`**, **`vl_warm`/`register_gpu_warm_callback`**, **`python-json-logger`**, **`test_pipeline_state.py`**. |
| **Orchestrator** | Поэтапный **`sp_runner.manage_sp_pipeline`** (retry, skip), константы **`SP_STAGE_*`** в **`config.py`**. |
| **shared_gpu_lock** | Опциональный **`warm_callback`** в **`GPUResourceManager.acquire`**. |

**Вручную на VPS:** применить DDL из **`init_db.sql`** к существующей **`clicks.db`** (или миграция), положить **`GeoLite2-Country.mmdb`** при необходимости fallback GEO, cron для **`recalc_shave.py`** и **`retry_postbacks.py`**.

### Сессия 13 (28.03.2026) — План 10–14 (добивка), секреты, UI

| Область | Изменение |
|---------|-----------|
| **Монорепа** | В git: **`secrets.enc.env`** + **`.sops.yaml`**; локально **`age/age.key`**. Опциональный plaintext: **`.secrets.env`** (или вывод `sops -d`) + **`.secrets.env.example`**. Код по-прежнему вызывает `load_dotenv(.../.secrets.env)` — при запуске через **`sops exec-env secrets.enc.env -- …`** переменные уже в **`os.environ`**. **ContentHub** `main.py`, **Orchestrator** `config.py`, **ShortsProject** `pipeline/config.py`, **PreLend** `internal_api/config.py`. **`GitHub/.gitignore`**: `.secrets.env`, `secrets.plain.env`, `age/`. |
| **ContentHub backend** | `backend/integrations/prelend_client.py` — шим к **Orchestrator**; **config_writer**: `git_config_log/show/revert`; **configs.py**: `GET /api/configs/history*`, `POST .../revert`; **advertisers**: `GET /api/advertisers/compare`; **analytics**: `GET /api/analytics/audit` → **require_admin**; **auth**: `require_operator_or_internal` для **POST /api/events**; **config**: `INTERNAL_EVENTS_KEY`. |
| **ContentHub frontend** | Вкладки **Сравнение по метрикам**, **История конфигов**; **AuditPage** + маршрут `/audit`; **api.ts** расширен; адаптив сайдбара/main. |
| **PreLend** | `GET /metrics` → поле **`by_advertiser`**; **ContentHubEvents.php** + postback → ContentHub при `CONTENTHUB_URL` / ключе. |
| **Orchestrator** | LLM-as-judge в evaluator, отложенный LLM в evolution по `pipeline_state`, дайджест + карточка + push в ContentHub, `LOG_FORMAT=json`. |
| **Тесты CH** | `pytest backend/tests/ -q` (без integration) → **33 passed** (актуально на момент обновления status). |

**Gitignore:** `ContentHub/.gitignore` — комментарий к порядку `.env`, `secrets.local.env`; дубликаты `__pycache__`/`backend/.env` убраны с хвоста файла.

### Сессия 12 (29.03.2026) — Code Review: Auth & Config Fixes

| Область | Изменение |
|---------|-----------|
| **`backend/config.py`** | **[HIGH]** SECRET_KEY: при `COOKIE_SECURE=true` (production) и отсутствии `CONTENTHUB_SECRET_KEY` → `EnvironmentError` вместо молчаливого временного ключа. В dev-mode (без COOKIE_SECURE) поведение не изменилось. |
| **`backend/api/routes/auth.py`** | **[MEDIUM]** `change_password`: `body: dict` → `ChangePasswordRequest(BaseModel)` с полями `old_password`, `new_password`. Автоматическая валидация Pydantic, корректная OpenAPI схема. |

**Контекст:** Часть полного code review экосистемы. Также рекомендовано: LIKE wildcard экранирование в будущем Audit Log endpoint (план сессии 13.2).

### Сессия 14 (29.03.2026) — Документация: права `PreLend/config/` и PUT рекламодателей

**Проблема:** при рабочем туннеле **:9090** и **`GET /health`** сохранение рекламодателей из ContentHub падало с **HTTP 500**, в **`detail`** — **`Permission denied: .../config/tmp….tmp`**.

**Причина на VPS:** **`prelend-internal-api`** (**`www-data`**) не может писать во временные файлы в **`config/`** (атомарная запись JSON).

**Действия:** исправление **`chown`/`chmod`** на сервере и закрепление в **`PreLend/deploy/deploy.sh`**; полная инструкция, smoke **curl PUT** и чеклист «как не повторять» — в **`PreLend/status.md`** (раздел **«ОБЯЗАТЕЛЬНО: права на каталог config/`»**, сессия **25**). В ContentHub в текст ошибки API добавлено поле **«Ответ API: …»** для диагностики (**`Orchestrator/integrations/prelend_client.py`**, **`config_writer`**).
