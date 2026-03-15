"""
api/routes/dashboard.py — главный дашборд.
"""

from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends

from db.connection import get_db
from services.auth import require_viewer
from services.metrics_collector import collect_dashboard

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("")
def get_dashboard(user: Annotated[dict, Depends(require_viewer)]):
    """
    Возвращает unified snapshot всех метрик.
    Приоритет: кэш из DB (обновляется фоновой задачей раз в 60 сек).
    Если кэш пустой — собирает сразу.
    """
    with get_db() as db:
        row = db.execute(
            "SELECT value_json, updated_at FROM metrics_cache WHERE key='dashboard'"
        ).fetchone()

    if row:
        return {"data": json.loads(row["value_json"]), "updated_at": row["updated_at"], "from_cache": True}

    # Кэш пуст — собираем напрямую
    data = collect_dashboard()
    return {"data": data, "updated_at": data["updated_at"], "from_cache": False}
