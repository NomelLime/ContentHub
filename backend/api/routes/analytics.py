"""
api/routes/analytics.py — воронка и аналитика.

GET /api/analytics/funnel?days=7    → воронка видео → конверсии
GET /api/analytics/audit?limit=50   → audit log действий через UI
GET /api/analytics/sp               → SP метрики за период
GET /api/analytics/pl               → PreLend метрики за период
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from db.connection import get_db
from services.auth import require_viewer
from services.metrics_collector import (
    collect_funnel,
    _collect_pl_summary,
    _collect_sp_summary,
)

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/funnel")
def get_funnel(
    days: int = Query(7, ge=1, le=90),
    user: Annotated[dict, Depends(require_viewer)] = None,
):
    return {"days": days, "funnel": collect_funnel(days=days)}


@router.get("/sp")
def get_sp_analytics(user: Annotated[dict, Depends(require_viewer)]):
    return _collect_sp_summary()


@router.get("/pl")
def get_pl_analytics(user: Annotated[dict, Depends(require_viewer)]):
    return _collect_pl_summary()


@router.get("/audit")
def get_audit_log(
    limit: int = Query(50, ge=1, le=500),
    project: str = Query(None),
    user: Annotated[dict, Depends(require_viewer)] = None,
):
    """Возвращает последние действия из audit_log."""
    with get_db() as db:
        if project:
            rows = db.execute(
                "SELECT * FROM audit_log WHERE project=? ORDER BY ts DESC LIMIT ?",
                (project, limit),
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT * FROM audit_log ORDER BY ts DESC LIMIT ?",
                (limit,),
            ).fetchall()
    return [dict(r) for r in rows]
