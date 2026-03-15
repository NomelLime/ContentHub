"""
api/ws/broadcaster.py — фоновая asyncio задача рассылки WebSocket событий.

Запускается при старте FastAPI через lifespan.
Каждые WS_BROADCAST_SEC секунд:
  1. Читает agent_memory.json (SP и PL)
  2. Читает notifications из orchestrator.db
  3. Сравнивает с предыдущим состоянием
  4. Пушит только дельты подписчикам

Это не блокирует event loop: все I/O операции выполняются в executor.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
from pathlib import Path
from typing import Any, Dict

import config as cfg
from api.ws.manager import manager
from services.agent_controller import get_sp_agents_status, get_pl_agents_status
from services.metrics_collector import collect_dashboard

logger = logging.getLogger(__name__)

# Предыдущие состояния для diff
_prev_agents:  Dict[str, Any] = {}
_prev_metrics: Dict[str, Any] = {}
_prev_alerts_id: int = 0


async def broadcast_loop() -> None:
    """Бесконечный цикл рассылки. Запускать как asyncio task."""
    global _prev_agents, _prev_metrics, _prev_alerts_id

    logger.info("[Broadcaster] Запущен, интервал %d сек", cfg.WS_BROADCAST_SEC)

    while True:
        try:
            await _tick()
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.warning("[Broadcaster] Ошибка тика: %s", exc)

        await asyncio.sleep(cfg.WS_BROADCAST_SEC)


async def _tick() -> None:
    global _prev_agents, _prev_metrics, _prev_alerts_id
    loop = asyncio.get_event_loop()

    # ── Агенты ────────────────────────────────────────────────────────────────
    agents_data = await loop.run_in_executor(None, _get_agents)
    agents_str  = json.dumps(agents_data, sort_keys=True)
    prev_str    = json.dumps(_prev_agents, sort_keys=True)

    if agents_str != prev_str:
        _prev_agents = agents_data
        await manager.broadcast("agents", agents_data)

    # ── Метрики (реже — раз в 60 сек через metrics_cache) ───────────────────
    # Реальный refresh делается metrics_updater (каждые METRICS_REFRESH_SEC сек)
    # Здесь просто читаем кэш из DB
    metrics_data = await loop.run_in_executor(None, _get_metrics_cache)
    if metrics_data and metrics_data != _prev_metrics:
        _prev_metrics = metrics_data
        await manager.broadcast("metrics", metrics_data)

    # ── Алерты ────────────────────────────────────────────────────────────────
    new_alerts, last_id = await loop.run_in_executor(None, _get_new_alerts, _prev_alerts_id)
    if new_alerts:
        _prev_alerts_id = last_id
        for alert in new_alerts:
            await manager.broadcast("alerts", alert)


def _get_agents() -> dict:
    sp = get_sp_agents_status()
    pl = get_pl_agents_status()
    return {"ShortsProject": sp, "PreLend": pl}


def _get_metrics_cache() -> dict:
    from db.connection import get_db
    try:
        with get_db() as db:
            row = db.execute(
                "SELECT value_json FROM metrics_cache WHERE key='dashboard'"
            ).fetchone()
            if row:
                return json.loads(row["value_json"])
    except Exception:
        pass
    return {}


def _get_new_alerts(last_id: int) -> tuple[list, int]:
    """Читает новые уведомления из orchestrator.db с id > last_id."""
    if not cfg.ORC_DB.exists():
        return [], last_id

    try:
        with sqlite3.connect(str(cfg.ORC_DB)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT id, level, category, message, created_at FROM notifications WHERE id > ? ORDER BY id",
                (last_id,),
            ).fetchall()
            if not rows:
                return [], last_id
            alerts = [dict(r) for r in rows]
            new_last_id = rows[-1]["id"]
            return alerts, new_last_id
    except Exception:
        return [], last_id
