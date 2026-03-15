"""
services/metrics_collector.py — агрегация метрик из всех проектов.

Читает:
  - ShortsProject/data/analytics.json
  - PreLend/data/clicks.db
  - Orchestrator/orchestrator.db

Возвращает unified dict для dashboard и funnel chart.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import config as cfg

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Dashboard — общая сводка
# ──────────────────────────────────────────────────────────────────────────────

def collect_dashboard() -> Dict[str, Any]:
    """
    Собирает данные для главного дашборда.
    Вызывается фоновой задачей каждые METRICS_REFRESH_SEC секунд.
    """
    result: Dict[str, Any] = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "sp":  _collect_sp_summary(),
        "pl":  _collect_pl_summary(),
        "orc": _collect_orc_summary(),
    }
    return result


def _collect_sp_summary() -> Dict:
    """Читает analytics.json ShortsProject и возвращает агрегат."""
    path = cfg.SP_ANALYTICS_FILE
    if not path.exists():
        return {"available": False}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("[MetricsCollector] SP analytics read error: %s", exc)
        return {"available": False}

    now = datetime.now(timezone.utc)
    cutoff_24h = now - timedelta(hours=24)
    cutoff_7d  = now - timedelta(days=7)

    total_views = 0
    total_likes = 0
    videos_24h  = 0
    videos_7d   = 0
    platform_views: Dict[str, int] = {}

    for stem, entry in data.items():
        if not isinstance(entry, dict):
            continue
        views     = entry.get("views", 0) or 0
        likes     = entry.get("likes", 0) or 0
        platform  = entry.get("platform", "unknown")
        upload_ts = entry.get("uploaded_at", "")

        total_views += views
        total_likes += likes
        platform_views[platform] = platform_views.get(platform, 0) + views

        if upload_ts:
            try:
                ts = datetime.fromisoformat(upload_ts.replace("Z", "+00:00"))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if ts >= cutoff_24h:
                    videos_24h += 1
                if ts >= cutoff_7d:
                    videos_7d += 1
            except Exception:
                pass

    top_platform = max(platform_views, key=platform_views.get, default="—") if platform_views else "—"

    return {
        "available":     True,
        "total_views":   total_views,
        "total_likes":   total_likes,
        "videos_24h":    videos_24h,
        "videos_7d":     videos_7d,
        "top_platform":  top_platform,
        "platform_views": platform_views,
        "total_videos":  len(data),
    }


def _collect_pl_summary() -> Dict:
    """Читает PreLend/data/clicks.db и возвращает агрегат за 24ч."""
    db_path = cfg.PL_CLICKS_DB
    if not db_path.exists():
        return {"available": False}

    try:
        with sqlite3.connect(str(db_path)) as conn:
            conn.row_factory = sqlite3.Row

            row = conn.execute("""
                SELECT
                    COUNT(*)                                                AS total_clicks,
                    SUM(CASE WHEN status = 'converted' THEN 1 ELSE 0 END)  AS conversions,
                    SUM(CASE WHEN status = 'bot'        THEN 1 ELSE 0 END)  AS bot_clicks,
                    (SELECT geo FROM clicks
                     WHERE ts >= datetime('now','-24 hours')
                     GROUP BY geo ORDER BY COUNT(*) DESC LIMIT 1)           AS top_geo
                FROM clicks
                WHERE ts >= datetime('now', '-24 hours')
            """).fetchone()

            clicks      = row["total_clicks"] or 0
            conversions = row["conversions"]  or 0
            bot_clicks  = row["bot_clicks"]   or 0
            top_geo     = row["top_geo"]      or "—"
            cr          = round(conversions / clicks, 4) if clicks > 0 else 0.0
            bot_pct     = round(bot_clicks  / clicks, 4) if clicks > 0 else 0.0

            return {
                "available":    True,
                "clicks_24h":   clicks,
                "conversions_24h": conversions,
                "cr_24h":       cr,
                "bot_pct_24h":  bot_pct,
                "top_geo":      top_geo,
            }
    except Exception as exc:
        logger.warning("[MetricsCollector] PL clicks.db read error: %s", exc)
        return {"available": False}


def _collect_orc_summary() -> Dict:
    """Читает orchestrator.db — зоны, последний план, патчи."""
    db_path = cfg.ORC_DB
    if not db_path.exists():
        return {"available": False}

    try:
        with sqlite3.connect(str(db_path)) as conn:
            conn.row_factory = sqlite3.Row

            zones = [dict(r) for r in conn.execute(
                "SELECT zone_name, enabled, confidence_score FROM zones"
            ).fetchall()]

            pending_patches = conn.execute(
                "SELECT COUNT(*) as cnt FROM pending_patches WHERE status='pending'"
            ).fetchone()["cnt"]

            last_plan = conn.execute(
                "SELECT summary, created_at, status FROM evolution_plans ORDER BY created_at DESC LIMIT 1"
            ).fetchone()

            return {
                "available":      True,
                "zones":          zones,
                "pending_patches": pending_patches,
                "last_plan": dict(last_plan) if last_plan else None,
            }
    except Exception as exc:
        logger.warning("[MetricsCollector] ORC DB read error: %s", exc)
        return {"available": False}


# ──────────────────────────────────────────────────────────────────────────────
# Funnel analytics
# ──────────────────────────────────────────────────────────────────────────────

def collect_funnel(days: int = 7) -> List[Dict]:
    """
    Строит воронку: видео → просмотры → клики PreLend → конверсии → доход.

    Связка осуществляется через video_funnel_links в contenthub.db.
    Если линков нет — возвращает данные SP и PL по отдельности.
    """
    from db.connection import get_db

    sp_data   = _collect_sp_summary()
    pl_data   = _collect_pl_summary()
    cutoff    = datetime.now(timezone.utc) - timedelta(days=days)

    # Читаем линки из contenthub.db
    with get_db() as db:
        links = db.execute(
            "SELECT sp_stem, platform, prelend_sub_id FROM video_funnel_links WHERE linked_at >= ?",
            (cutoff.isoformat(),),
        ).fetchall()

    if not links:
        # Нет линков — возвращаем агрегированные данные без детализации по видео
        return [{
            "level": "aggregate",
            "sp_views":     sp_data.get("total_views", 0),
            "pl_clicks":    pl_data.get("clicks_24h", 0),
            "pl_conversions": pl_data.get("conversions_24h", 0),
            "pl_cr":        pl_data.get("cr_24h", 0),
            "note": "Нет cross-project линков. Добавьте sub_id в uploader.py.",
        }]

    # Есть линки — строим детальную воронку
    # (заглушка: детальная реализация будет в Этапе 12)
    result = []
    for link in links:
        result.append({
            "sp_stem":      link["sp_stem"],
            "platform":     link["platform"],
            "prelend_sub_id": link["prelend_sub_id"],
        })
    return result
