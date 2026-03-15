"""
api/routes/agents.py — управление агентами.

GET  /api/agents              → список всех агентов и статусов
POST /api/agents/{project}/{name}/stop   → отправить стоп-сигнал
POST /api/agents/{project}/{name}/start  → отправить старт-сигнал
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from services.agent_controller import (
    get_pl_agents_status,
    get_sp_agents_status,
    send_start_request,
    send_stop_request,
)
from services.auth import log_audit, require_operator, require_viewer

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.get("")
def list_agents(user: Annotated[dict, Depends(require_viewer)]):
    """Возвращает статусы всех агентов SP и PL."""
    return {
        "ShortsProject": get_sp_agents_status(),
        "PreLend":        get_pl_agents_status(),
    }


@router.post("/{project}/{agent_name}/stop")
def stop_agent(
    project: str,
    agent_name: str,
    user: Annotated[dict, Depends(require_operator)],
):
    ok = send_stop_request(project, agent_name)
    if not ok:
        raise HTTPException(400, detail=f"Агент {agent_name} не найден в проекте {project}")
    log_audit(user, "agent_stop", project, {"agent": agent_name})
    return {"success": True, "message": f"Стоп-сигнал отправлен → {project}/{agent_name}"}


@router.post("/{project}/{agent_name}/start")
def start_agent(
    project: str,
    agent_name: str,
    user: Annotated[dict, Depends(require_operator)],
):
    ok = send_start_request(project, agent_name)
    if not ok:
        raise HTTPException(400, detail=f"Агент {agent_name} не найден в проекте {project}")
    log_audit(user, "agent_start", project, {"agent": agent_name})
    return {"success": True, "message": f"Старт-сигнал отправлен → {project}/{agent_name}"}
