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
from pathlib import Path
from typing import Dict, List

import config as cfg

logger = logging.getLogger(__name__)

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
    statuses = memory.get("agent_statuses", {})

    result = []
    for agent in SP_AGENTS:
        info = statuses.get(agent, {})
        result.append({
            "name":       agent,
            "project":    "ShortsProject",
            "status":     info.get("status", "UNKNOWN"),
            "updated_at": info.get("updated_at"),
            "error":      info.get("last_error"),
        })
    return result


def get_pl_agents_status() -> List[Dict]:
    """Возвращает статусы агентов PreLend."""
    memory = _read_memory(cfg.PL_AGENT_MEMORY)
    statuses = memory.get("agent_statuses", {})

    result = []
    for agent in PL_AGENTS:
        info = statuses.get(agent, {})
        result.append({
            "name":       agent,
            "project":    "PreLend",
            "status":     info.get("status", "UNKNOWN"),
            "updated_at": info.get("updated_at"),
            "error":      info.get("last_error"),
        })
    return result


def send_stop_request(project: str, agent_name: str) -> bool:
    """
    Посылает сигнал остановки агенту через agent_memory.json.
    """
    agent_upper = agent_name.upper()

    if project == "ShortsProject":
        if agent_upper not in SP_AGENTS:
            return False
        path = cfg.SP_AGENT_MEMORY
    elif project == "PreLend":
        if agent_upper not in PL_AGENTS:
            return False
        path = cfg.PL_AGENT_MEMORY
    else:
        return False

    memory = _read_memory(path)
    memory.setdefault("control", {})[f"stop_request.{agent_upper}"] = True
    _write_memory(path, memory)
    logger.info("[AgentController] Стоп-сигнал → %s/%s", project, agent_upper)
    return True


def send_start_request(project: str, agent_name: str) -> bool:
    """
    Посылает сигнал запуска агенту через agent_memory.json.
    """
    agent_upper = agent_name.upper()

    if project == "ShortsProject":
        if agent_upper not in SP_AGENTS:
            return False
        path = cfg.SP_AGENT_MEMORY
    elif project == "PreLend":
        if agent_upper not in PL_AGENTS:
            return False
        path = cfg.PL_AGENT_MEMORY
    else:
        return False

    memory = _read_memory(path)
    ctrl = memory.setdefault("control", {})
    ctrl[f"start_request.{agent_upper}"] = True
    ctrl.pop(f"stop_request.{agent_upper}", None)  # снимаем стоп если был
    _write_memory(path, memory)
    logger.info("[AgentController] Старт-сигнал → %s/%s", project, agent_upper)
    return True
