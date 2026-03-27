"""
api/routes/operator_commands.py — чтение трейса команд оператора (Orchestrator policy_command_trace.jsonl).
"""

from __future__ import annotations

import json
from typing import Annotated, Any, Dict, List

from fastapi import APIRouter, Depends, Query

import config as cfg
from services.auth import require_viewer

router = APIRouter(prefix="/api/operator-commands", tags=["operator-commands"])


def _read_trace_tail(limit: int) -> List[Dict[str, Any]]:
    path = cfg.ORC_POLICY_TRACE
    if not path.exists():
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    lines = [ln for ln in text.splitlines() if ln.strip()]
    tail = lines[-limit:]
    out: List[Dict[str, Any]] = []
    for line in tail:
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            out.append({"_parse_error": True, "_raw": line[:500]})
    return out


@router.get("/trace")
def get_policy_command_trace(
    user: Annotated[dict, Depends(require_viewer)],
    limit: int = Query(500, ge=1, le=5000, description="Последние N записей JSONL"),
):
    """
    Возвращает последние записи из policy_command_trace.jsonl (Orchestrator).
    """
    rows = _read_trace_tail(limit)
    return {
        "count": len(rows),
        "limit": limit,
        "source": str(cfg.ORC_POLICY_TRACE),
        "events": rows,
    }
