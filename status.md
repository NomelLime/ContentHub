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
│   │   │   ├── configs.py             # GET/PUT /api/configs/*
│   │   │   ├── advertisers.py         # CRUD рекламодателей PreLend
│   │   │   ├── analytics.py           # GET /api/analytics/*, /pl?period_hours=, /plan-quality
│   │   │   └── ws_route.py            # WebSocket /ws (JWT auth через ?token=)
│   │   └── ws/
│   │       └── broadcaster.py         # asyncio broadcast loop с diff-логикой
│   ├── services/
│   │   ├── auth.py                    # JWT create/verify, bcrypt, RBAC depends
│   │   ├── metrics_collector.py       # Агрегация метрик; PreLend + geo_breakdown из /metrics
│   │   ├── config_reader.py           # Чтение конфигов (SP, PreLend, Orchestrator)
│   │   ├── config_writer.py           # Запись конфигов + approve/reject патчей (→ 409 при race)
│   │   └── agent_controller.py        # Запись флагов в agent_memory.json
│   └── tests/
│       ├── conftest.py                # Изолированная БД, фикстуры admin/viewer
│       ├── test_auth.py               # login, rate-limit, RBAC, logout, refresh
│       ├── test_patches.py            # list, approve (viewer→403), nonexistent→409
│       └── test_token_rotation.py     # Token rotation: replay protection, role в ответе
└── frontend/
    └── src/
        ├── lib/
        │   └── api.ts                 # HTTP клиент: accessToken (memory), role (memory), clearAuth
        ├── hooks/
        │   └── useWebSocket.ts        # WS хук: getAccessToken() при каждом коннекте
        ├── pages/
        │   ├── LoginPage.tsx          # auth.login() → setAccessToken(at, role) in-memory
        │   ├── DashboardPage.tsx      # getUserRole() [FIX#3]
        │   ├── PatchesPage.tsx        # getUserRole() + DiffViewer [FIX#3]
        │   ├── ConfigPage.tsx         # getUserRole() [FIX#3]
        │   ├── AnalyticsPage.tsx      # FunnelChart + PlGeoTable (PreLend по ГЕО)
        │   └── UsersPage.tsx          # CRUD пользователей
        └── App.tsx                    # RequireAuth + Layout с getUserRole() [FIX#3]
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
| `admin` | Все функции включая управление пользователями (`/api/auth/users`) |
| `operator` | Запись конфигов, approve/reject патчей, управление splits и агентами |
| `viewer` | Только чтение: dashboard, аналитика, список агентов и патчей |

---

## ENV (.env.example)

```env
# JWT
CONTENTHUB_SECRET_KEY=your-secret-key-here   # python3 -c "import secrets; print(secrets.token_hex(32))"
ACCESS_TOKEN_EXPIRE_MIN=60
REFRESH_TOKEN_EXPIRE_DAYS=30

# Пути к проектам
GITHUB_ROOT=/path/to/projects    # Обязательно — иначе EnvironmentError при старте

# Web-сервер
CONTENTHUB_HOST=0.0.0.0
CONTENTHUB_PORT=8000

# CORS: задать конкретный origin, НЕ "*" (несовместимо с allow_credentials=True)
ALLOWED_ORIGINS=http://localhost:5173

# Cookie secure (false для localhost, true для HTTPS)
COOKIE_SECURE=false

# PreLend Internal API (VPS → SSH tunnel → localhost:9090)
PL_INTERNAL_API_URL=http://localhost:9090
PL_INTERNAL_API_KEY=   # python3 -c "import secrets; print(secrets.token_hex(32))"
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
- [ ] `python -m pytest ContentHub/backend/tests/ -q` — запустить на деплое
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

**Эксплуатация:** на VPS нужны актуальный PreLend Internal API и права на `config/` + `data/`; ключ `PL_INTERNAL_API_KEY` совпадает с ContentHub `backend/.env`.

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
