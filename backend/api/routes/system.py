"""
api/routes/system.py — системные эндпоинты (health всей экосистемы).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from services.auth import require_viewer
from services.health_checker import collect_system_health

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/health")
def system_health(user: Annotated[dict, Depends(require_viewer)]):
    """Единый снимок здоровья PreLend, ShortsProject, Orchestrator и GPU."""
    return collect_system_health()
