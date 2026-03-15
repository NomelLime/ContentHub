"""
main.py — FastAPI entrypoint для ContentHub.

Запуск:
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload

Production:
    uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1
"""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

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


# ──────────────────────────────────────────────────────────────────────────────
# Lifespan: инициализация и фоновые задачи
# ──────────────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Проверка безопасности: предупредить если используется дефолтный SECRET_KEY
    if cfg.SECRET_KEY == cfg._DEFAULT_SECRET:
        logger.warning(
            "[ContentHub] ⚠️  ВНИМАНИЕ: используется дефолтный SECRET_KEY! "
            "Задайте переменную CONTENTHUB_SECRET_KEY в .env перед продовым деплоем."
        )

    # Инициализация БД
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
    """Обновляет кэш метрик каждые METRICS_REFRESH_SEC секунд."""
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

# CORS — ограничен через cfg.ALLOWED_ORIGINS (по умолчанию localhost:5173 для dev)
# В продакшне задать ALLOWED_ORIGINS=https://yourdomain.com в .env
app.add_middleware(
    CORSMiddleware,
    allow_origins=cfg.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
