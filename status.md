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
│   │   │   ├── analytics.py           # GET /api/analytics/*, /plan-quality
│   │   │   └── ws_route.py            # WebSocket /ws (JWT auth через ?token=)
│   │   └── ws/
│   │       └── broadcaster.py         # asyncio broadcast loop с diff-логикой
│   ├── services/
│   │   ├── auth.py                    # JWT create/verify, bcrypt, RBAC depends
│   │   ├── metrics_collector.py       # Агрегация метрик из 3 проектов
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
        │   ├── AnalyticsPage.tsx      # FunnelChart
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
