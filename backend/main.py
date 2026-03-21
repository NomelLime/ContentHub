"""
main.py — FastAPI entrypoint для ContentHub.

Запуск:
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload

Production:
    uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1

[FIX#7]  Expired sessions cleanup: раз в час в metrics_refresh_loop().
[FIX#16] CORS: allow_methods и allow_headers явно ограничены.
         Проверка что ALLOWED_ORIGINS не содержит "*" (несовместимо с allow_credentials=True).
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

# ⚠️ Убедиться что backend/ первым в PATH (чтобы избежать конфликта с Orchestrator's db/)
_backend_dir = Path(__file__).parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

# ⚠️ ВАЖНО: удалить Orchestrator из sys.path чтобы избежать конфликта с db/connection.py
_orchestrator_dir = _backend_dir.parent / "Orchestrator"
if str(_orchestrator_dir) in sys.path:
    sys.path.remove(str(_orchestrator_dir))
# Также удаляем его родительские директории если они там есть
sys.path = [p for p in sys.path if not p.endswith("Orchestrator") and "Orchestrator" not in p]

# ⚠️ КРИТИЧНО: load_dotenv() в САМОМ НАЧАЛЕ ДО импорта config и других модулей!
from dotenv import load_dotenv

# Явно указываем путь к .env — ищем в директории где лежит этот файл (backend/)
_env_file = _backend_dir / ".env"
load_dotenv(dotenv_path=_env_file)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import config as cfg
from db.connection import init_db, get_db
from services.metrics_collector import collect_dashboard
from api.ws.broadcaster import broadcast_loop

# Роутеры
from api.routes import (
    dashboard,
    agents,
    patches,
    configs,
    advertisers,
    analytics,
    auth,
    ws_route,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def _agent_log(hypothesis_id: str, location: str, message: str, data: dict) -> None:
    # region agent log
    try:
        payload = {
            "sessionId": "0398bc",
            "runId": "pre-fix",
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data,
            "timestamp": int(time.time() * 1000),
        }
        log_path = Path(__file__).resolve().parent.parent / "debug-0398bc.log"
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass
    # endregion


# ──────────────────────────────────────────────────────────────────────────────
# Lifespan: инициализация и фоновые задачи
# ──────────────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    _agent_log(
        "H4",
        "backend/main.py:lifespan_entry",
        "Lifespan started",
        {
            "contenthubDb": str(cfg.CONTENTHUB_DB),
            "dbParentExists": cfg.CONTENTHUB_DB.parent.exists(),
            "host": cfg.HOST,
            "port": cfg.PORT,
        },
    )
    # Проверка безопасности: предупредить если используется временный SECRET_KEY
    if getattr(cfg, "_is_temp_secret", False):
        logger.warning(
            "[ContentHub] ⚠️  ВНИМАНИЕ: CONTENTHUB_SECRET_KEY не задан — "
            "сгенерирован временный ключ. При рестарте все сессии сбросятся. "
            "Задайте переменную CONTENTHUB_SECRET_KEY в .env!"
        )

    # [FIX#16] Проверка CORS — "*" несовместим с allow_credentials=True
    if "*" in cfg.ALLOWED_ORIGINS:
        logger.error(
            "[ContentHub] ⛔ ALLOWED_ORIGINS содержит '*' — несовместимо с "
            "allow_credentials=True! Браузеры заблокируют запросы с credentials. "
            "Задайте конкретный origin в .env: ALLOWED_ORIGINS=https://yourdomain.com"
        )

    # Инициализация БД
    _agent_log(
        "H3",
        "backend/main.py:init_db_source",
        "Resolved init_db import source",
        {
            "module": getattr(init_db, "__module__", ""),
            "sourceFile": inspect.getsourcefile(init_db) or "",
        },
    )
    init_db()
    logger.info("[ContentHub] БД инициализирована: %s", cfg.CONTENTHUB_DB)

    # Запускаем фоновые задачи
    broadcaster_task = asyncio.create_task(broadcast_loop())
    metrics_task     = asyncio.create_task(metrics_refresh_loop())

    logger.info("[ContentHub] Запущен. Порт: %s", cfg.PORT)
    yield

    # Завершение
    broadcaster_task.cancel()
    metrics_task.cancel()
    try:
        await broadcaster_task
    except asyncio.CancelledError:
        pass
    try:
        await metrics_task
    except asyncio.CancelledError:
        pass
    logger.info("[ContentHub] Остановлен.")


async def metrics_refresh_loop():
    """
    Обновляет кэш метрик каждые METRICS_REFRESH_SEC секунд.

    [FIX#7] Раз в ~60 итераций (~1 час при 60с интервале) удаляет истёкшие сессии.
    Предотвращает неограниченный рост таблицы sessions при refresh token rotation.
    """
    _cleanup_counter = 0
    # Один тик = METRICS_REFRESH_SEC секунд. Очищаем раз в час.
    _cleanup_every_n = max(1, 3600 // max(cfg.METRICS_REFRESH_SEC, 1))

    while True:
        try:
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(None, collect_dashboard)
            with get_db() as db:
                db.execute(
                    "INSERT OR REPLACE INTO metrics_cache (key, value_json, updated_at) VALUES (?,?,?)",
                    ("dashboard", json.dumps(data), datetime.now(timezone.utc).isoformat()),
                )
                db.commit()
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.warning("[MetricsRefresh] Ошибка: %s", exc)

        # [FIX#7] Периодическая очистка истёкших сессий
        _cleanup_counter += 1
        if _cleanup_counter >= _cleanup_every_n:
            _cleanup_counter = 0
            try:
                with get_db() as db:
                    expired = db.execute(
                        "DELETE FROM sessions WHERE expires_at < ?",
                        (datetime.now(timezone.utc).isoformat(),),
                    ).rowcount
                    if expired:
                        logger.info("[Cleanup] Удалено истёкших сессий: %d", expired)
                    db.commit()
            except Exception as exc:
                logger.warning("[Cleanup] Ошибка очистки сессий: %s", exc)

        await asyncio.sleep(cfg.METRICS_REFRESH_SEC)


# ──────────────────────────────────────────────────────────────────────────────
# Приложение
# ──────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="ContentHub API",
    description="Централизованная панель управления ShortsProject + PreLend + Orchestrator",
    version="1.0.0",
    lifespan=lifespan,
)

# [FIX#16] CORS — явно ограниченные методы и заголовки вместо allow_methods=["*"]
# allow_credentials=True несовместимо с allow_origins=["*"] — убедиться что ALLOWED_ORIGINS
# не содержит "*" (проверяется в lifespan выше и при старте)
app.add_middleware(
    CORSMiddleware,
    allow_origins     = cfg.ALLOWED_ORIGINS,
    allow_credentials = True,
    # Явный список вместо ["*"] — не пропускаем экзотические методы (TRACE, CONNECT и др.)
    allow_methods     = ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    # Явный список заголовков — не пропускаем произвольные заголовки
    allow_headers     = ["Authorization", "Content-Type"],
)

# Регистрация роутеров
app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(agents.router)
app.include_router(patches.router)
app.include_router(configs.router)
app.include_router(advertisers.router)
app.include_router(analytics.router)
app.include_router(ws_route.router)


@app.get("/")
def root():
    return {
        "project": "ContentHub",
        "version": "1.0.0",
        "docs":    "/docs",
    }


@app.get("/health")
def health():
    return {"status": "ok", "ts": datetime.now(timezone.utc).isoformat()}