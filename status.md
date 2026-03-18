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
│   │   │   ├── auth.py                # POST /api/auth/login, /logout, /me
│   │   │   ├── dashboard.py           # GET /api/dashboard (метрики всех проектов)
│   │   │   ├── agents.py              # GET /api/agents, POST /api/agents/{name}/start|stop
│   │   │   ├── patches.py             # GET/POST /api/patches/{id}/approve|reject
│   │   │   ├── configs.py             # GET/PUT /api/configs/{project}/{section}
│   │   │   ├── advertisers.py         # CRUD /api/advertisers
│   │   │   ├── analytics.py           # GET /api/analytics/funnel, /api/analytics/splits
│   │   │   └── ws_route.py            # GET /ws (WebSocket endpoint)
│   │   └── ws/
│   │       ├── manager.py             # ConnectionManager (broadcast, connect, disconnect)
│   │       └── broadcaster.py         # asyncio фоновая задача: diff → push каждые 5с
│   ├── services/
│   │   ├── auth.py                    # JWT создание/проверка, bcrypt hash/verify
│   │   ├── config_reader.py           # Чтение SP .env, PL конфигов через Internal API
│   │   ├── config_writer.py           # Запись SP .env (атомично), PL конфигов через Internal API
│   │   ├── metrics_collector.py       # Агрегация: analytics.json + PL API + orchestrator.db
│   │   └── agent_controller.py        # SP: agent_memory.json; PL: через Internal API
│   │   # prelend_client используется из Orchestrator/integrations/ через sys.path (config.py)
│   └── models/
│       └── __init__.py
└── frontend/
    ├── index.html
    ├── package.json
    ├── vite.config.ts
    ├── tailwind.config.js
    ├── tsconfig.json
    ├── src/
    │   ├── main.tsx
    │   ├── App.tsx                    # Router: /dashboard, /patches, /config, /analytics, /users
    │   ├── index.css
    │   ├── lib/
    │   │   └── api.ts                 # fetch-обёртки + JWT заголовки
    │   ├── hooks/
    │   │   └── useWebSocket.ts        # WebSocket hook (auto-reconnect, delta merge)
    │   ├── components/
    │   │   ├── Dashboard/MetricCard.tsx       # Карточка метрики (views, CR, ROI)
    │   │   ├── AgentPanel/AgentPanel.tsx      # Статус-карточки агентов + кнопки старт/стоп
    │   │   ├── PatchReview/PatchReview.tsx    # diff-вьюер + approve/reject кнопки
    │   │   ├── ConfigEditor/ConfigEditor.tsx  # Форм-редактор конфига по секциям
    │   │   ├── AdvertiserManager/AdvertiserManager.tsx  # CRUD таблица advertisers.json
    │   │   ├── FunnelChart/FunnelChart.tsx    # Видео → просмотры → клики → конверсии
    │   │   └── AlertFeed/AlertFeed.tsx        # Real-time поток событий через WebSocket
    │   └── pages/
    │       ├── DashboardPage.tsx      # /dashboard — общие метрики + агенты
    │       ├── PatchesPage.tsx        # /patches — список патчей, approve/reject
    │       ├── ConfigPage.tsx         # /config — редактор конфигов по проектам
    │       ├── AnalyticsPage.tsx      # /analytics — воронка + split-тесты
    │       ├── LoginPage.tsx          # /login
    │       └── UsersPage.tsx          # /users (только admin)
```

---

## API ENDPOINTS

| Метод | URL | Описание |
|-------|-----|----------|
| POST | `/api/auth/login` | JWT авторизация |
| GET | `/api/auth/me` | Текущий пользователь |
| GET | `/api/dashboard` | Агрегированные метрики SP + PL + ORC |
| GET | `/api/agents` | Статус всех агентов из agent_memory.json |
| POST | `/api/agents/{name}/start` | Пишет `start_request.{name}` в agent_memory |
| POST | `/api/agents/{name}/stop` | Пишет `stop_request.{name}` в agent_memory |
| GET | `/api/patches` | Список pending_patches из orchestrator.db |
| POST | `/api/patches/{id}/approve` | Обновляет статус → approved |
| POST | `/api/patches/{id}/reject` | Обновляет статус → rejected |
| GET | `/api/configs/{project}/{section}` | Читает секцию конфига проекта |
| PUT | `/api/configs/{project}/{section}` | Атомичная запись конфига + audit_log |
| GET | `/api/advertisers` | Список из advertisers.json |
| POST | `/api/advertisers` | Добавить рекламодателя |
| PUT | `/api/advertisers/{id}` | Обновить рекламодателя |
| DELETE | `/api/advertisers/{id}` | Удалить рекламодателя |
| GET | `/api/analytics/funnel` | Данные воронки из funnel_events |
| GET | `/api/analytics/splits` | Split-тесты из PreLend/config/splits.json |
| PUT | `/api/analytics/splits` | Обновить splits.json (operator+) |
| WS | `/ws` | WebSocket: delta-push каждые 5с |

---

## БАЗА ДАННЫХ (backend/contenthub.db)

```sql
users           (id, username UNIQUE, password_hash, role, created_at, last_login)
sessions        (id, user_id, token_hash, created_at, expires_at)
audit_log       (id, ts, user_id, action, project, detail_json)
metrics_cache   (key PRIMARY KEY, value_json, updated_at)
video_funnel_links (id, sp_stem, platform, video_url, prelend_sub_id, linked_at)
```

---

## WEBSOCKET BROADCASTER

Фоновая asyncio задача (каждые 5 секунд):
- Читает `agent_memory.json` SP и PL → статусы агентов
- Читает `notifications` из orchestrator.db → алерты
- Diff от предыдущего состояния → push только дельты подключённым клиентам

---

## УПРАВЛЕНИЕ КОНФИГАМИ (из UI)

| Что меняется | Как хранится | Механизм |
|---|---|---|
| SP pipeline config | `.env` файл SP | `config_writer.write_env_var()` → git commit |
| SP settings (JSON) | `settings.json` | `os.replace()` атомично → git commit |
| PL advertisers | `advertisers.json` на VPS | `prelend_client.write_advertisers()` → PUT /config/advertisers → git commit на VPS |
| PL geo_data | `geo_data.json` на VPS | `prelend_client.write_geo_data()` → PUT /config/geo_data |
| PL splits | `splits.json` на VPS | `prelend_client.write_splits()` → PUT /config/splits |
| ORC config | `.env` ORC | `config_writer.write_env_var()` |

Изменения конфигов, требующие рестарта → флаг `requires_restart: true` в ответе API + кнопка «Рестарт» в UI.

---

## РОЛИ ПОЛЬЗОВАТЕЛЕЙ

| Роль | Доступ |
|------|--------|
| `admin` | Все функции включая управление пользователями (`/api/auth/users`) |
| `operator` | Запись конфигов, approve/reject патчей, управление splits и агентами |
| `viewer` | Только чтение: dashboard, аналитика, список агентов и патчей |

---

## СТАТУС РАЗРАБОТКИ

**Дата создания:** 15.03.2026
**Фаза:** Backend + Frontend реализованы. Следующий шаг: деплой + настройка `.env`.

[x] Этап 1 — Backend FastAPI
    (main.py, config.py, db/schema.sql, все API routes, WebSocket broadcaster)
[x] Этап 2 — Frontend React + Vite
    (6 страниц, 7 компонентов, useWebSocket hook, api.ts, Tailwind UI)
[x] Этап 3 — Интеграция с PreLend Internal API
    (prelend_client.py, рефакторинг всех сервисов)
[ ] Этап 4 — Деплой + первый запуск
    (запуск: `uvicorn backend.main:app --port 8000`)
[ ] Этап 5 — Тесты API endpoints

---

## ИСТОРИЯ СЕССИЙ

### Сессия 1 (15.03.2026) — Полная реализация

Создан новый проект с нуля как часть плана 15 фич.

**Backend:**
- FastAPI приложение с JWT auth (bcrypt + python-jose)
- SQLite DB с 5 таблицами
- 8 API route-модулей + WebSocket endpoint
- Сервисный слой: config_reader/writer (атомичная запись), metrics_collector (агрегация из 3 проектов), agent_controller (запись флагов в agent_memory.json)
- WebSocket ConnectionManager + asyncio broadcaster с diff-логикой

**Frontend:**
- React 18 + Vite + TypeScript + Tailwind CSS
- 6 страниц: Dashboard, Patches, Config, Analytics, Login, Users
- 7 компонентов: MetricCard, AgentPanel, PatchReview, ConfigEditor, AdvertiserManager, FunnelChart, AlertFeed
- `useWebSocket.ts` — авто-reconnect, delta merge в React state
- `api.ts` — типизированные fetch-обёртки с JWT Bearer заголовком

### Сессия 3 (18.03.2026) — Безопасность перед боевым запуском

| Файл | Проблема | Исправление |
|------|----------|-------------|
| `backend/config.py` | Дефолтный `SECRET_KEY` допускал старт с известным ключом | Авто-генерация `secrets.token_hex(32)` если ключ не задан; флаг `_is_temp_secret`; WARNING в лог |
| `backend/main.py` | Сравнение с `_DEFAULT_SECRET` (побочный эффект) | Проверка `getattr(cfg, '_is_temp_secret', False)` |
| `backend/api/routes/ws_route.py` | WebSocket без аутентификации — любой в LAN мог подключиться | JWT проверка через `?token=<JWT>` query param до `accept()`. Код `4001` при отказе |
| `frontend/src/hooks/useWebSocket.ts` | Токен не передавался на WS | `localStorage.getItem('access_token')` добавлен в URL. При `code=4001` — нет авторекконекта |
| `backend/api/routes/configs.py` | `PUT /PreLend/settings` принимал `body: dict` без типизации | Pydantic модели `PLAlertsUpdate` + `PLSettingsUpdate` с числовыми границами. FastAPI 422 при невалидных типах |
| `backend/api/routes/auth.py` | Нет защиты от brute-force на `/login` | In-memory rate limiter: 5 попыток за 60 сек на username. 429 при превышении |

**Исправления:**

| Файл | Проблема | Исправление |
|------|----------|-------------|
| `backend/config.py` | Хардкод `C:\Users\lemon\...` в GITHUB_ROOT | `EnvironmentError` если не задан в `.env` |
| `backend/services/auth.py` | `import json as _json` внутри функции `log_audit()` | Перенесён на верхний уровень |

**Рефакторинг PreLend → Internal API:**

PreLend теперь на VPS — прямой доступ к его файлам с локальной машины невозможен.
Все операции чтения/записи теперь идут через HTTP к PreLend Internal API (порт 9090).

| Файл | Что изменилось |
|------|----------------|
| `services/prelend_client.py` (NEW) | Копия HTTP-клиента (из Orchestrator). Singleton `get_client()` |
| `services/config_reader.py` | `read_pl_*()` → `client.get_*()` вместо прямого чтения файлов |
| `services/config_writer.py` | `write_pl_*()` → `client.write_*()` вместо `atomic_write_json` + git commit |
| `services/agent_controller.py` | PL агенты: `get_pl_agents_status()` и `send_stop/start_request()` через API. SP агенты — по-прежнему через локальный agent_memory.json |
| `services/metrics_collector.py` | `_collect_pl_summary()` → `client.get_metrics()` вместо прямого sqlite3 |
| `backend/config.py` | + `PL_INTERNAL_API_URL`, `PL_INTERNAL_API_KEY` |
| `backend/.env.example` | + секция PreLend Internal API |

---

## ЗАПУСК

```bash
# Backend
cd ContentHub/backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Frontend
cd ContentHub/frontend
npm install
npm run dev        # dev: http://localhost:5173
npm run build      # prod: dist/
```

**Первый пользователь:** создаётся напрямую в SQLite (`INSERT INTO users ...`) или через `POST /api/auth/users` от имени существующего admin-пользователя. Открытой регистрации нет.

---

## ENV (.env.example)

```env
# JWT
CONTENTHUB_SECRET_KEY=your-secret-key-here
ACCESS_TOKEN_EXPIRE_MIN=60
REFRESH_TOKEN_EXPIRE_DAYS=30

# Пути к проектам
GITHUB_ROOT=/path/to/projects    # Обязательно — иначе EnvironmentError при старте

# Web-сервер
CONTENTHUB_HOST=0.0.0.0
CONTENTHUB_PORT=8000

# CORS (для dev — localhost:5173)
ALLOWED_ORIGINS=http://localhost:5173

# PreLend Internal API (VPS → SSH tunnel → localhost:9090)
# SSH tunnel: ssh -N -L 9090:127.0.0.1:9090 user@vps-ip
PL_INTERNAL_API_URL=http://localhost:9090
PL_INTERNAL_API_KEY=your-shared-secret-key-here
```
