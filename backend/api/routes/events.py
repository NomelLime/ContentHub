"""
api/routes/events.py — приём системных событий для WebSocket-рассылки.
"""

from __future__ import annotations

import json
import time
from typing import Annotated, Any, Dict

from fastapi import APIRouter, Depends

from db.connection import get_db
from services.auth import require_operator_or_internal

router = APIRouter(prefix="/api/events", tags=["events"])


@router.post("")
def push_event(
    body: Dict[str, Any],
    user: Annotated[dict, Depends(require_operator_or_internal)],
):
    """Сохраняет событие для broadcaster (WS)."""
    source = str(body.get("source") or "unknown")
    event_type = str(body.get("event_type") or "alert")
    payload = body.get("payload") or {}
    with get_db() as db:
        db.execute(
            "INSERT INTO system_events (source, event_type, payload, created_at) VALUES (?,?,?,?)",
            (source, event_type, json.dumps(payload, ensure_ascii=False), time.time()),
        )
        db.commit()
    return {"ok": True}
