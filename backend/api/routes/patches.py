"""
api/routes/patches.py — управление патчами кода (одобрение/отклонение).

GET  /api/patches             → список pending патчей с diff
POST /api/patches/{id}/approve → одобрить (пишет в orchestrator.db)
POST /api/patches/{id}/reject  → отклонить

Orchestrator подхватывает approved патчи на следующем цикле.
Telegram /approve_N продолжает работать параллельно.
"""

from __future__ import annotations

from typing import Annotated, List

from fastapi import APIRouter, Depends, HTTPException

from services.auth import log_audit, require_operator, require_viewer
from services.config_reader import read_orc_pending_patches
from services.config_writer import approve_patch, reject_patch

router = APIRouter(prefix="/api/patches", tags=["patches"])


@router.get("", response_model=List[dict])
def list_patches(user: Annotated[dict, Depends(require_viewer)]):
    """Возвращает pending и approved патчи из orchestrator.db."""
    return read_orc_pending_patches()


@router.post("/{patch_id}/approve")
def approve(
    patch_id: int,
    user: Annotated[dict, Depends(require_operator)],
):
    ok = approve_patch(patch_id)
    if not ok:
        raise HTTPException(404, detail=f"Патч #{patch_id} не найден или уже обработан")
    log_audit(user, "patch_approve", "Orchestrator", {"patch_id": patch_id})
    return {"success": True, "message": f"Патч #{patch_id} одобрен. Orchestrator применит на следующем цикле."}


@router.post("/{patch_id}/reject")
def reject(
    patch_id: int,
    user: Annotated[dict, Depends(require_operator)],
):
    ok = reject_patch(patch_id)
    if not ok:
        raise HTTPException(404, detail=f"Патч #{patch_id} не найден или уже обработан")
    log_audit(user, "patch_reject", "Orchestrator", {"patch_id": patch_id})
    return {"success": True, "message": f"Патч #{patch_id} отклонён."}
