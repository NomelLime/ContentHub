"""
services/agent_controller.py — управление агентами через agent_memory.json.

Принцип: ContentHub не вызывает агентов напрямую (разные процессы).
Вместо этого пишет сигналы в agent_memory.json.
Агенты проверяют эти ключи в своём run() цикле.

Ключи:
  stop_request.AGENT_NAME  = True   → агент завершает работу
  start_request.AGENT_NAME = True   → crew.py запускает агента
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import time as time_mod
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import config as cfg

logger = logging.getLogger(__name__)

# RUNNING/WAITING без свежего heartbeat в agent_memory → ContentHub покажет UNKNOWN (процесс мог умереть)
_SP_STATUS_STALE_MINUTES = int(os.getenv("SP_AGENT_STATUS_STALE_MINUTES", "25"))


def _parse_iso_dt(value: Optional[str]) -> Optional[datetime]:
    if not value or not isinstance(value, str):
        return None
    s = value.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


def _primary_status_token(raw: str) -> str:
    if not raw or not isinstance(raw, str):
        return "UNKNOWN"
    return raw.split(":")[0].strip().upper()


def _age_seconds_utc(since: Optional[datetime]) -> Optional[float]:
    if since is None:
        return None
    return (datetime.now(timezone.utc) - since).total_seconds()

# Известные агенты ShortsProject
SP_AGENTS = [
    "DIRECTOR", "SENTINEL", "SCOUT", "CURATOR", "VISIONARY",
    "NARRATOR", "EDITOR", "STRATEGIST", "GUARDIAN",
    "ACCOUNTANT", "PUBLISHER", "COMMANDER", "TREND_SCOUT",
]

# Известные агенты PreLend
PL_AGENTS = ["COMMANDER", "ANALYST", "MONITOR", "OFFER_ROTATOR"]


def _read_memory(path: Path) -> Dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_memory(path: Path, data: Dict) -> None:
    """Атомарная запись agent_memory.json."""
    text = json.dumps(data, ensure_ascii=False, indent=2)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        os.write(fd, text.encode("utf-8"))
        os.close(fd)
        os.replace(tmp, str(path))
    except Exception:
        try:
            os.close(fd)
        except Exception:
            pass
        try:
            os.unlink(tmp)
        except Exception:
            pass
        raise


def get_sp_agents_status() -> List[Dict]:
    """
    Возвращает статусы агентов ShortsProject из agent_memory.json.
    """
    memory = _read_memory(cfg.SP_AGENT_MEMORY)
    statuses = memory.get("agent_statuses") or {}
    agents_flat = memory.get("agents") or {}
    kv = memory.get("kv") or {}
    if not isinstance(kv, dict):
        kv = {}
    human_map = kv.get("agent_human_detail") or {}
    if not isinstance(human_map, dict):
        human_map = {}
    status_ts_map = kv.get("agent_status_updated_at") or {}
    if not isinstance(status_ts_map, dict):
        status_ts_map = {}

    stale_sec = max(60, _SP_STATUS_STALE_MINUTES * 60)
    result = []
    for agent in SP_AGENTS:
        per_agent_ts = status_ts_map.get(agent) or status_ts_map.get(agent.upper())
        per_agent_ts = per_agent_ts if isinstance(per_agent_ts, str) else None

        info = statuses.get(agent, {}) if isinstance(statuses, dict) else {}
        if isinstance(info, dict) and info.get("status"):
            status = info.get("status", "UNKNOWN")
            updated_at = info.get("updated_at")
            err = info.get("last_error")
            ts_for_stale = updated_at if isinstance(updated_at, str) else per_agent_ts
        else:
            raw = agents_flat.get(agent) if isinstance(agents_flat, dict) else None
            if isinstance(raw, str):
                status = raw
                updated_at = per_agent_ts or memory.get("saved_at")
                err = None
                # saved_at обновляется при любом save — для «протухшего RUNNING» нужен только per-agent ts
                ts_for_stale = per_agent_ts
            else:
                status = "UNKNOWN"
                updated_at = None
                err = None
                ts_for_stale = None

        detail = human_map.get(agent) or human_map.get(agent.upper())
        detail = detail if detail else None

        prim = _primary_status_token(status)
        if prim in ("RUNNING", "WAITING"):
            age = None
            if ts_for_stale:
                age = _age_seconds_utc(_parse_iso_dt(ts_for_stale))
            # Нет метки v2 (agent_status_updated_at) — ориентируемся на mtime файла (слабый эвристик)
            if age is None:
                try:
                    age = time_mod.time() - cfg.SP_AGENT_MEMORY.stat().st_mtime
                except OSError:
                    age = None
            if age is not None and age > stale_sec:
                old_line = status
                status = "UNKNOWN"
                hint = (
                    f"Устаревший снимок (>{_SP_STATUS_STALE_MINUTES} мин без обновления). "
                    f"Процесс мог быть остановлен. Было: {old_line}"
                )
                detail = f"{hint}\n{detail}" if detail else hint
                err = err or "stale_status"

        result.append({
            "name":       agent,
            "project":    "ShortsProject",
            "status":     status,
            "updated_at": updated_at,
            "error":      err,
            "detail":     detail,
        })
    return result


def get_pl_agents_status() -> List[Dict]:
    """Возвращает статусы агентов PreLend через Internal API."""
    from integrations.prelend_client import get_client
    client = get_client()
    if not client.is_available():
        # API недоступен — возвращаем агентов со статусом UNKNOWN
        return [
            {"name": agent, "project": "PreLend", "status": "UNKNOWN",
             "updated_at": None, "error": "PreLend API недоступен", "detail": None}
            for agent in PL_AGENTS
        ]
    return client.get_agents()


def send_stop_request(project: str, agent_name: str) -> bool:
    """Посылает сигнал остановки агенту через agent_memory.json (SP) или Internal API (PL)."""
    agent_upper = agent_name.upper()

    if project == "ShortsProject":
        if agent_upper not in SP_AGENTS:
            return False
        path = cfg.SP_AGENT_MEMORY
        memory = _read_memory(path)
        memory.setdefault("control", {})[f"stop_request.{agent_upper}"] = True
        _write_memory(path, memory)
        logger.info("[AgentController] Стоп-сигнал → %s/%s", project, agent_upper)
        return True

    elif project == "PreLend":
        if agent_upper not in PL_AGENTS:
            return False
        from integrations.prelend_client import get_client
        ok = get_client().stop_agent(agent_upper)
        if ok:
            logger.info("[AgentController] Стоп-сигнал → %s/%s (via API)", project, agent_upper)
        return ok

    return False


def send_start_request(project: str, agent_name: str) -> bool:
    """Посылает сигнал запуска агенту через agent_memory.json (SP) или Internal API (PL)."""
    agent_upper = agent_name.upper()

    if project == "ShortsProject":
        if agent_upper not in SP_AGENTS:
            return False
        path = cfg.SP_AGENT_MEMORY
        memory = _read_memory(path)
        ctrl = memory.setdefault("control", {})
        ctrl[f"start_request.{agent_upper}"] = True
        ctrl.pop(f"stop_request.{agent_upper}", None)
        _write_memory(path, memory)
        logger.info("[AgentController] Старт-сигнал → %s/%s", project, agent_upper)
        return True

    elif project == "PreLend":
        if agent_upper not in PL_AGENTS:
            return False
        from integrations.prelend_client import get_client
        ok = get_client().start_agent(agent_upper)
        if ok:
            logger.info("[AgentController] Старт-сигнал → %s/%s (via API)", project, agent_upper)
        return ok

    return False
