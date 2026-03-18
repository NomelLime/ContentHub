"""
api/routes/patches.py — управление патчами кода (одобрение/отклонение).

GET  /api/patches             → список pending патчей с diff
GET  /api/patches/{id}/diff   → полный diff + original/patched code для UI
POST /api/patches/{id}/approve → одобрить (пишет в orchestrator.db)
POST /api/patches/{id}/reject  → отклонить

Orchestrator подхватывает approved патчи на следующем цикле.
Telegram /approve_N продолжает работать параллельно.
"""

from __future__ import annotations

import sqlite3
from typing import Annotated, List

from fastapi import APIRouter, Depends, HTTPException

import config as cfg
from services.auth import log_audit, require_operator, require_viewer
from services.config_reader import read_orc_pending_patches
from services.config_writer import approve_patch, reject_patch

router = APIRouter(prefix="/api/patches", tags=["patches"])


@router.get("", response_model=List[dict])
def list_patches(user: Annotated[dict, Depends(require_viewer)]):
    """Возвращает pending и approved патчи из orchestrator.db."""
    return read_orc_pending_patches()


@router.get("/{patch_id}/diff")
def get_patch_diff(
    patch_id: int,
    user: Annotated[dict, Depends(require_viewer)],
):
    """
    Возвращает полный diff и код патча для отображения в diff-viewer UI.
    Включает: unified diff, original_code, patched_code, метаданные.
    """
    if not cfg.ORC_DB.exists():
        raise HTTPException(503, detail="Orchestrator DB недоступна")

    with sqlite3.connect(str(cfg.ORC_DB)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """SELECT id, plan_id, repo, file_path, goal, status,
                      diff_preview, original_code, patched_code,
                      created_at, approved_at, applied_at, apply_result
               FROM pending_patches WHERE id = ?""",
            (patch_id,),
        ).fetchone()

    if not row:
        raise HTTPException(404, detail=f"Патч #{patch_id} не найден")

    return dict(row)


@router.post("/{patch_id}/approve")
def approve(
    patch_id: int,
    user: Annotated[dict, Depends(require_operator)],
):
    ok = approve_patch(patch_id)
    if not ok:
        raise HTTPException(409, detail="Патч уже обработан или не найден")
    log_audit(user, "patch_approve", "Orchestrator", {"patch_id": patch_id})
    return {"success": True, "message": f"Патч #{patch_id} одобрен. Orchestrator применит на следующем цикле."}


@router.post("/{patch_id}/reject")
def reject(
    patch_id: int,
    user: Annotated[dict, Depends(require_operator)],
):
    ok = reject_patch(patch_id)
    if not ok:
        raise HTTPException(409, detail="Патч уже обработан или не найден")
    log_audit(user, "patch_reject", "Orchestrator", {"patch_id": patch_id})
    return {"success": True, "message": f"Патч #{patch_id} отклонён."}
