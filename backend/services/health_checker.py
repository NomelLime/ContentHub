"""
services/health_checker.py — агрегированное состояние PreLend, ShortsProject, Orchestrator, GPU.

Каждая секция изолирована: сбой одного источника не ломает остальные.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import config as cfg

logger = logging.getLogger(__name__)


def _get_pl_client():
    """Точка расширения для тестов (patch)."""
    from integrations.prelend_client import get_client

    return get_client()


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _collect_prelend() -> Dict[str, Any]:
    """Метрики и доступность PreLend через Internal API."""
    out: Dict[str, Any] = {
        "status": "unknown",
        "api_available": False,
        "clicks_24h": 0,
        "conversions_24h": 0,
        "bot_pct": 0.0,
        "landing_up_count": 0,
        "landing_total": 0,
        "response_ms": None,
    }
    try:
        t0 = time.perf_counter()
        client = _get_pl_client()
        health = client.get_health()
        ms = int((time.perf_counter() - t0) * 1000)
        out["response_ms"] = ms

        if health is None:
            out["status"] = "down"
            return out

        out["api_available"] = True
        metrics = client.get_metrics(period_hours=24)
        out["clicks_24h"] = int(metrics.get("total_clicks") or 0)
        out["conversions_24h"] = int(metrics.get("conversions") or 0)
        bot_raw = metrics.get("bot_pct")
        if bot_raw is not None:
            # [FIX] PreLend /metrics всегда возвращает bot_pct как проценты (0–100).
            # Было: эвристика "> 1 → делим на 100" — ломается на 1.5% (это 1.5%, не 150%).
            # Стало: всегда делим на 100 → доля (0.0–1.0).
            out["bot_pct"] = round(float(bot_raw) / 100.0, 4)

        landing = health.get("landing") if isinstance(health, dict) else None
        if isinstance(landing, dict):
            out["landing_up_count"] = int(landing.get("up_count") or 0)
            out["landing_total"] = int(landing.get("total") or 0)
        elif cfg.PL_CLICKS_DB.exists():
            try:
                with sqlite3.connect(str(cfg.PL_CLICKS_DB)) as c:
                    row = c.execute(
                        "SELECT SUM(CASE WHEN is_up = 1 THEN 1 ELSE 0 END) AS upc, COUNT(*) AS tot "
                        "FROM landing_status"
                    ).fetchone()
                    if row and row[1]:
                        out["landing_up_count"] = int(row[0] or 0)
                        out["landing_total"] = int(row[1] or 0)
            except Exception:
                pass

        st = "ok"
        if out["landing_total"] > 0 and out["landing_up_count"] < out["landing_total"]:
            st = "degraded"
        out["status"] = st
    except TimeoutError:
        out["status"] = "down"
    except Exception as exc:
        logger.debug("[health] prelend: %s", exc)
        out["status"] = "down"
    return out


def _collect_shorts_project() -> Dict[str, Any]:
    """Состояние агентов и загрузок ShortsProject по локальным файлам."""
    out: Dict[str, Any] = {
        "status": "unknown",
        "agents_running": 0,
        "agents_total": 0,
        "agents_in_error": [],
        "quarantined_accounts": [],
        "pipeline_running": False,
        "last_upload_at": None,
        "uploads_24h": 0,
    }
    try:
        mem_path = cfg.SP_AGENT_MEMORY
        if mem_path.exists():
            mem = json.loads(mem_path.read_text(encoding="utf-8"))
            statuses = mem.get("agent_statuses") or {}
            if isinstance(statuses, dict) and statuses:
                for name, st in statuses.items():
                    if not isinstance(st, dict):
                        continue
                    out["agents_total"] += 1
                    raw = (st.get("status") or "").lower()
                    if raw in ("running", "ok", "idle"):
                        out["agents_running"] += 1
                    elif raw in ("error", "failed", "crashed"):
                        out["agents_in_error"].append(str(name))
            else:
                for k, v in mem.items():
                    if isinstance(k, str) and k.startswith("agent.") and k.endswith(".status"):
                        out["agents_total"] += 1
                        sv = str(v).lower()
                        if sv in ("running", "ok", "idle"):
                            out["agents_running"] += 1
                        elif sv in ("error", "failed", "crashed"):
                            out["agents_in_error"].append(k)

        state_file = cfg.SHORTS_PROJECT_DIR / "data" / "pipeline_state.json"
        if state_file.exists():
            st = json.loads(state_file.read_text(encoding="utf-8"))
            out["pipeline_running"] = st.get("finished_at") is None and bool(st.get("stages"))

        acc_root = cfg.SP_ACCOUNTS_ROOT
        if acc_root.exists():
            for p in acc_root.iterdir():
                if not p.is_dir():
                    continue
                cj = p / "config.json"
                if not cj.exists():
                    continue
                try:
                    c = json.loads(cj.read_text(encoding="utf-8"))
                    if c.get("quarantine") or c.get("quarantined"):
                        out["quarantined_accounts"].append(p.name)
                except Exception:
                    pass

        analytics_path = cfg.SP_ANALYTICS_FILE
        if analytics_path.exists():
            aj = json.loads(analytics_path.read_text(encoding="utf-8"))
            uploads = aj.get("uploads") or []
            if isinstance(uploads, list):
                since = time.time() - 86400
                last_ts = 0.0
                n24 = 0
                for u in uploads:
                    if not isinstance(u, dict):
                        continue
                    ts = float(u.get("ts") or u.get("timestamp") or 0)
                    if ts >= since:
                        n24 += 1
                    if ts > last_ts:
                        last_ts = ts
                out["uploads_24h"] = n24
                if last_ts > 0:
                    out["last_upload_at"] = datetime.fromtimestamp(last_ts, tz=timezone.utc).isoformat()

        if out["agents_total"] == 0:
            out["status"] = "down"
        elif len(out["agents_in_error"]) >= 2:
            out["status"] = "degraded"
        elif len(out["agents_in_error"]) == 1:
            out["status"] = "degraded"
        else:
            out["status"] = "ok"
    except Exception as exc:
        logger.debug("[health] shorts_project: %s", exc)
        out["status"] = "unknown"
    return out


def _zone_frozen_from_policies(conn: sqlite3.Connection, zone_name: str) -> bool:
    row = conn.execute(
        "SELECT value_json FROM operator_policies WHERE key = ?",
        (f"freeze_zone_{zone_name}",),
    ).fetchone()
    if not row:
        return False
    try:
        v = json.loads(row[0] or "false")
        return bool(v)
    except Exception:
        return False


def _collect_orchestrator() -> Dict[str, Any]:
    """Зона, планы и очереди из orchestrator.db (локальный файл)."""
    out: Dict[str, Any] = {
        "status": "unknown",
        "last_cycle_at": None,
        "zones": {},
        "pending_patches": 0,
        "pending_commands": 0,
    }
    db_path = cfg.ORC_DB
    if not db_path.exists():
        out["status"] = "unknown"
        return out
    try:
        with sqlite3.connect(str(db_path)) as conn:
            conn.row_factory = sqlite3.Row
            last_plan = conn.execute(
                "SELECT created_at FROM evolution_plans ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
            if last_plan:
                out["last_cycle_at"] = last_plan["created_at"]

            zones_rows = conn.execute(
                "SELECT zone_name, enabled, confidence_score FROM zones"
            ).fetchall()
            zones_dict: Dict[str, Any] = {}
            for r in zones_rows:
                zn = r["zone_name"]
                zones_dict[zn] = {
                    "enabled": bool(r["enabled"]),
                    "score": int(r["confidence_score"] or 0),
                    "frozen": _zone_frozen_from_policies(conn, zn),
                }
            out["zones"] = zones_dict

            pp = conn.execute(
                "SELECT COUNT(*) AS c FROM pending_patches WHERE status = 'pending'"
            ).fetchone()
            out["pending_patches"] = int(pp["c"] if pp else 0)

            oc = conn.execute(
                "SELECT COUNT(*) AS c FROM operator_commands WHERE status = 'pending'"
            ).fetchone()
            out["pending_commands"] = int(oc["c"] if oc else 0)

        out["status"] = "ok"
    except Exception as exc:
        logger.debug("[health] orchestrator: %s", exc)
        out["status"] = "unknown"
    return out


def _collect_gpu() -> Dict[str, Any]:
    """
    Состояние GPU-lock (in-process недоступно из ContentHub).
    При наличии файла статуса — читаем; иначе заглушка.
    """
    out: Dict[str, Any] = {"lock_holder": None, "queue_size": 0}
    status_file = cfg.SHORTS_PROJECT_DIR / "data" / "gpu_status.json"
    try:
        if status_file.exists():
            data = json.loads(status_file.read_text(encoding="utf-8"))
            out["lock_holder"] = data.get("lock_holder")
            out["queue_size"] = int(data.get("queue_size") or 0)
    except Exception:
        pass
    return out


def collect_system_health() -> Dict[str, Any]:
    """
    Собирает полный снимок здоровья системы.

    Returns:
        dict с ключами timestamp, prelend, shorts_project, orchestrator, gpu.
    """
    return {
        "timestamp": _iso_now(),
        "prelend": _collect_prelend(),
        "shorts_project": _collect_shorts_project(),
        "orchestrator": _collect_orchestrator(),
        "gpu": _collect_gpu(),
    }
