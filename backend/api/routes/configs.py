"""
api/routes/configs.py — управление конфигами всех проектов.

GET  /api/configs/ShortsProject          → все секции конфига SP
GET  /api/configs/ShortsProject/{section}→ конкретная секция
PUT  /api/configs/ShortsProject/{section}→ обновить env-переменные секции

GET  /api/configs/PreLend/settings       → settings.json
PUT  /api/configs/PreLend/settings       → обновить settings.json

GET  /api/configs/Orchestrator/zones     → зоны доверия
"""

from __future__ import annotations

from typing import Annotated, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from services.auth import log_audit, require_operator, require_viewer
from services.config_reader import (
    SP_ENV_SECTIONS,
    read_orc_zones,
    read_pl_settings,
    read_sp_env,
)
from services.config_writer import write_pl_settings, write_sp_env

router = APIRouter(prefix="/api/configs", tags=["configs"])


# ──────────────────────────────────────────────────────────────────────────────
# ShortsProject
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/ShortsProject")
def get_sp_config(user: Annotated[dict, Depends(require_viewer)]):
    """Возвращает все доступные секции конфига SP с текущими значениями."""
    return read_sp_env()


@router.get("/ShortsProject/{section}")
def get_sp_config_section(
    section: str,
    user: Annotated[dict, Depends(require_viewer)],
):
    all_sections = read_sp_env()
    if section not in all_sections:
        raise HTTPException(404, detail=f"Секция '{section}' не найдена. Доступны: {list(all_sections.keys())}")
    return {section: all_sections[section]}


class SpEnvUpdate(BaseModel):
    updates: Dict[str, str]   # {ENV_KEY: value}


@router.put("/ShortsProject/{section}")
def update_sp_config(
    section: str,
    body: SpEnvUpdate,
    user: Annotated[dict, Depends(require_operator)],
):
    """
    Обновляет env-переменные секции SP.
    Разрешены только ключи из SP_ENV_SECTIONS (whitelist).
    """
    if section not in SP_ENV_SECTIONS:
        raise HTTPException(404, detail=f"Секция '{section}' не найдена")

    allowed_keys = {field[0] for field in SP_ENV_SECTIONS[section]}
    forbidden = set(body.updates.keys()) - allowed_keys
    if forbidden:
        raise HTTPException(400, detail=f"Недопустимые ключи: {forbidden}. Разрешены: {allowed_keys}")

    write_sp_env(body.updates, username=user["username"])
    log_audit(user, "config_write", "ShortsProject", {"section": section, "keys": list(body.updates.keys())})
    return {"success": True, "updated": list(body.updates.keys())}


# ──────────────────────────────────────────────────────────────────────────────
# PreLend
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/PreLend/settings")
def get_pl_settings(user: Annotated[dict, Depends(require_viewer)]):
    return read_pl_settings()


@router.put("/PreLend/settings")
def update_pl_settings(
    body: dict,
    user: Annotated[dict, Depends(require_operator)],
):
    # Базовая валидация: известные ключи
    current = read_pl_settings()
    if not isinstance(body, dict):
        raise HTTPException(400, detail="Ожидается JSON объект")
    # Merge: не заменяем весь файл, только переданные ключи
    merged = {**current, **body}
    write_pl_settings(merged, username=user["username"])
    log_audit(user, "config_write", "PreLend", {"keys": list(body.keys())})
    return {"success": True, "settings": merged}


# ──────────────────────────────────────────────────────────────────────────────
# Orchestrator
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/Orchestrator/zones")
def get_orc_zones(user: Annotated[dict, Depends(require_viewer)]):
    return read_orc_zones()
