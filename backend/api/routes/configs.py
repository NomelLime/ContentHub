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

import logging
from enum import Enum
from typing import Annotated, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from services.auth import log_audit, require_operator, require_viewer
from services.config_reader import (
    SP_ENV_SECTIONS,
    read_orc_zones,
    read_pl_settings,
    read_sp_env,
)
from services.config_writer import (
    git_config_log,
    git_config_revert_to_commit,
    git_config_show,
    list_config_history_targets,
    write_pl_settings,
    write_sp_env,
)

logger = logging.getLogger(__name__)

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


# ── Pydantic-модели для PreLend settings ─────────────────────────────────────

class PLAlertsUpdate(BaseModel):
    """Числовые пороги алертов. FastAPI вернёт 422 при невалидных типах."""
    bot_pct_per_hour:       Optional[float] = Field(None, ge=0, le=100)
    offgeo_pct_per_hour:    Optional[float] = Field(None, ge=0, le=100)
    shave_threshold_pct:    Optional[float] = Field(None, ge=0, le=100)
    landing_slow_ms:        Optional[int]   = Field(None, ge=100, le=30_000)
    landing_down_alert_min: Optional[int]   = Field(None, ge=1,   le=1_440)


class PLSettingsUpdate(BaseModel):
    """Разрешённые поля для обновления settings.json PreLend."""
    alerts:              Optional[PLAlertsUpdate] = None
    default_offer_url:   Optional[str]            = Field(None, max_length=500)
    cloak_template:      Optional[str]            = Field(None, max_length=100)
    test_conversion_day: Optional[int]            = Field(None, ge=0, le=6)


@router.put("/PreLend/settings")
def update_pl_settings(
    body: PLSettingsUpdate,
    user: Annotated[dict, Depends(require_operator)],
):
    """
    Обновляет PreLend/config/settings.json.

    Принимает только строго типизированные поля (Pydantic 422 при невалидных значениях).
    Для alerts — deep merge: передаётся только delta, остальные ключи сохраняются.
    """
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(400, detail="Пустое тело запроса")

    current = read_pl_settings()

    merged = dict(current)
    for key, value in updates.items():
        if key == "alerts" and isinstance(value, dict) and isinstance(merged.get("alerts"), dict):
            merged["alerts"] = {**merged["alerts"], **value}
        else:
            merged[key] = value

    try:
        write_pl_settings(merged, username=user["username"])
    except RuntimeError as exc:
        logger.warning("[configs] write_pl_settings: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    log_audit(user, "config_write", "PreLend", {"keys": list(updates.keys())})
    return {"success": True, "settings": merged}


# ──────────────────────────────────────────────────────────────────────────────
# Orchestrator
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/Orchestrator/zones")
def get_orc_zones(user: Annotated[dict, Depends(require_viewer)]):
    return read_orc_zones()


# ──────────────────────────────────────────────────────────────────────────────
# История конфигов (git)
# ──────────────────────────────────────────────────────────────────────────────


class ConfigHistoryTarget(str, Enum):
    sp_env = "sp_env"
    pl_settings = "pl_settings"
    pl_advertisers = "pl_advertisers"


@router.get("/history/targets")
def config_history_targets(user: Annotated[dict, Depends(require_viewer)]):
    """Список ключей файлов, для которых доступны log/show/revert."""
    return {"targets": list_config_history_targets()}


@router.get("/history")
def config_history_log(
    target: ConfigHistoryTarget = Query(..., description="sp_env | pl_settings | pl_advertisers"),
    limit: int = Query(40, ge=1, le=200),
    user: Annotated[dict, Depends(require_viewer)] = None,
):
    """Коммиты, менявшие выбранный конфиг."""
    try:
        entries = git_config_log(target.value, limit=limit)
    except KeyError:
        raise HTTPException(400, detail="Неизвестный target") from None
    return {"target": target.value, "commits": entries}


@router.get("/history/show")
def config_history_show(
    target: ConfigHistoryTarget = Query(...),
    commit: str = Query(..., min_length=7, max_length=64),
    user: Annotated[dict, Depends(require_viewer)] = None,
):
    """Текст файла на выбранном коммите (git show)."""
    try:
        content = git_config_show(target.value, commit)
    except KeyError:
        raise HTTPException(400, detail="Неизвестный target") from None
    except RuntimeError as exc:
        raise HTTPException(404, detail=str(exc)) from exc
    return {"target": target.value, "commit": commit, "content": content}


class ConfigHistoryRevertBody(BaseModel):
    target: ConfigHistoryTarget
    commit: str = Field(..., min_length=7, max_length=64)


@router.post("/history/revert")
def config_history_revert(
    body: ConfigHistoryRevertBody,
    user: Annotated[dict, Depends(require_operator)],
):
    """
    Восстанавливает файл из коммита (git checkout + commit).
    operator/admin. Для PreLend дополнительно вызывается Internal API при успехе.
    """
    try:
        git_config_revert_to_commit(body.target.value, body.commit, username=user["username"])
    except KeyError:
        raise HTTPException(400, detail="Неизвестный target") from None
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(502, detail=str(exc)) from exc

    log_audit(
        user,
        "config_revert",
        "ShortsProject" if body.target == ConfigHistoryTarget.sp_env else "PreLend",
        {"target": body.target.value, "commit": body.commit[:12]},
    )
    return {"success": True, "target": body.target.value, "commit": body.commit}
