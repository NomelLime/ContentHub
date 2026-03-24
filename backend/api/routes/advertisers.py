"""
api/routes/advertisers.py — CRUD для рекламодателей PreLend.

GET    /api/advertisers           → список всех рекламодателей
GET    /api/advertisers/{id}      → один рекламодатель
POST   /api/advertisers           → создать нового
PUT    /api/advertisers/{id}      → обновить (rate, geo, status, ...)
DELETE /api/advertisers/{id}      → удалить (soft: status → 'deleted')

GET    /api/advertisers/geo-data  → geo_data.json
PUT    /api/advertisers/geo-data  → обновить geo_data.json
"""

from __future__ import annotations

import uuid
from typing import Annotated, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from services.auth import log_audit, require_operator, require_viewer
from services.config_reader import read_pl_advertisers, read_pl_geo_data, read_pl_templates
from services.config_writer import (
    write_pl_advertiser,
    write_pl_advertisers,
    write_pl_geo_data,
)

router = APIRouter(prefix="/api/advertisers", tags=["advertisers"])


# ──────────────────────────────────────────────────────────────────────────────
# Рекламодатели
# ──────────────────────────────────────────────────────────────────────────────

@router.get("", response_model=List[dict])
def list_advertisers(user: Annotated[dict, Depends(require_viewer)]):
    advertisers = read_pl_advertisers()
    # Скрываем секреты HMAC в ответе
    return [_mask_secrets(a) for a in advertisers]


@router.get("/geo-data")
def get_geo_data(user: Annotated[dict, Depends(require_viewer)]):
    return read_pl_geo_data()


@router.get("/templates")
def get_templates(user: Annotated[dict, Depends(require_viewer)]):
    return read_pl_templates()


@router.get("/{advertiser_id}")
def get_advertiser(advertiser_id: str, user: Annotated[dict, Depends(require_viewer)]):
    advertisers = read_pl_advertisers()
    adv = next((a for a in advertisers if a.get("id") == advertiser_id), None)
    if not adv:
        raise HTTPException(404, detail=f"Рекламодатель '{advertiser_id}' не найден")
    return _mask_secrets(adv)


class AdvertiserCreate(BaseModel):
    name:       str
    url:        str
    rate:       float
    geo:        List[str]   = []
    device:     List[str]   = []
    time_from:  str         = "00:00"
    time_to:    str         = "23:59"
    template:   str         = "expert_review"
    status:     str         = "active"
    backup_offer_id: Optional[str] = None
    hmac_secret:     Optional[str] = None
    allowed_ips:     List[str]     = []
    max_postbacks_per_min: int     = 60


@router.post("", status_code=201)
def create_advertiser(
    body: AdvertiserCreate,
    user: Annotated[dict, Depends(require_operator)],
):
    advertisers = read_pl_advertisers()
    new_adv = body.model_dump()
    new_adv["id"] = f"adv_{uuid.uuid4().hex[:8]}"
    advertisers.append(new_adv)
    write_pl_advertisers(advertisers, username=user["username"])
    log_audit(user, "advertiser_create", "PreLend", {"id": new_adv["id"], "name": new_adv["name"]})
    return {**_mask_secrets(new_adv), "id": new_adv["id"]}


class AdvertiserUpdate(BaseModel):
    name:        Optional[str]       = None
    url:         Optional[str]       = None
    rate:        Optional[float]     = None
    geo:         Optional[List[str]] = None
    device:      Optional[List[str]] = None
    time_from:   Optional[str]       = None
    time_to:     Optional[str]       = None
    template:    Optional[str]       = None
    status:      Optional[str]       = None
    backup_offer_id:        Optional[str]       = None
    hmac_secret:            Optional[str]       = None
    allowed_ips:            Optional[List[str]] = None
    max_postbacks_per_min:  Optional[int]       = None


@router.put("/{advertiser_id}")
def update_advertiser(
    advertiser_id: str,
    body: AdvertiserUpdate,
    user: Annotated[dict, Depends(require_operator)],
):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    ok = write_pl_advertiser(advertiser_id, updates, username=user["username"])
    if not ok:
        # Различаем "не найден" и "есть, но не удалось синхронно сохранить".
        exists = any(a.get("id") == advertiser_id for a in read_pl_advertisers())
        if exists:
            raise HTTPException(
                500,
                detail=(
                    f"Не удалось сохранить рекламодателя '{advertiser_id}': "
                    "источник данных PreLend не подтвердил изменение. "
                    "Проверьте Internal API / туннель."
                ),
            )
        raise HTTPException(404, detail=f"Рекламодатель '{advertiser_id}' не найден")
    log_audit(user, "advertiser_update", "PreLend", {"id": advertiser_id, "fields": list(updates.keys())})
    return {"success": True, "id": advertiser_id, "updated": list(updates.keys())}


@router.delete("/{advertiser_id}")
def delete_advertiser(
    advertiser_id: str,
    user: Annotated[dict, Depends(require_operator)],
):
    # Soft delete: меняем status → 'deleted'
    ok = write_pl_advertiser(advertiser_id, {"status": "deleted"}, username=user["username"])
    if not ok:
        raise HTTPException(404, detail=f"Рекламодатель '{advertiser_id}' не найден")
    log_audit(user, "advertiser_delete", "PreLend", {"id": advertiser_id})
    return {"success": True, "id": advertiser_id}


@router.put("/geo-data")
def update_geo_data(
    body: Dict[str, dict],
    user: Annotated[dict, Depends(require_operator)],
):
    """Обновляет geo_data.json. body: {ISO2: {currency, city, reviewer}}"""
    write_pl_geo_data(body, username=user["username"])
    log_audit(user, "geo_data_update", "PreLend", {"countries": list(body.keys())})
    return {"success": True, "countries": len(body)}


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _mask_secrets(adv: dict) -> dict:
    """Маскирует HMAC-секрет в ответе API."""
    result = dict(adv)
    if result.get("hmac_secret"):
        result["hmac_secret"] = "***"
    return result
