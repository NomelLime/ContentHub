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
