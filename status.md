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
│   │   ├── config_reader.py           # Чтение config.py (env-backed), settings.json, advertisers.json
│   │   ├── config_writer.py           # Атомичная запись (паттерн os.replace) + git commit
│   │   ├── metrics_collector.py       # Агрегация: analytics.json + clicks.db + orchestrator.db
│   │   └── agent_controller.py        # stop_request.*/start_request.* в agent_memory.json
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
| GET | `/api/analytics/splits` | Split-тесты из splits.json |
| WS | `/ws` | WebSocket: delta-push каждые 5с |

---

## БАЗА ДАННЫХ (contenthub.db)

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
| PL advertisers | `advertisers.json` | `os.replace()` → audit_log |
| PL geo_data | `geo_data.json` | `os.replace()` → audit_log |
| PL splits | `splits.json` | `os.replace()` → audit_log |
| ORC config | `.env` ORC | `config_writer.write_env_var()` |

Изменения конфигов, требующие рестарта → флаг `requires_restart: true` в ответе API + кнопка «Рестарт» в UI.

---

## РОЛИ ПОЛЬЗОВАТЕЛЕЙ

| Роль | Доступ |
|------|--------|
| `admin` | Все функции включая управление пользователями (`/users`) |
| `viewer` | Только чтение: dashboard, аналитика, список агентов и патчей |

---

## СТАТУС РАЗРАБОТКИ

**Дата создания:** 15.03.2026
**Фаза:** Backend + Frontend реализованы. Следующий шаг: деплой + настройка `.env`.

[x] Этап 1 — Backend FastAPI
    (main.py, config.py, db/schema.sql, все API routes, WebSocket broadcaster)
[x] Этап 2 — Frontend React + Vite
    (6 страниц, 7 компонентов, useWebSocket hook, api.ts, Tailwind UI)
[ ] Этап 3 — Деплой + первый запуск
    (запуск: `uvicorn backend.main:app --port 8000`)
[ ] Этап 4 — Тесты API endpoints

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

**Первый пользователь:** создаётся через `POST /api/auth/register` или напрямую в SQLite.

---

## ENV (.env.example)

```env
# JWT
SECRET_KEY=your-secret-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=480

# Пути к проектам
SP_DIR=../ShortsProject
PL_DIR=../PreLend
ORC_DIR=../Orchestrator

# CORS (для dev — localhost:5173)
ALLOWED_ORIGINS=http://localhost:5173
```
