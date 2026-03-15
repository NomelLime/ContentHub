"""
api/routes/analytics.py — воронка и аналитика.

GET  /api/analytics/funnel?days=7   → воронка видео → конверсии
GET  /api/analytics/audit?limit=50  → audit log действий через UI
GET  /api/analytics/sp              → SP метрики за период
GET  /api/analytics/pl              → PreLend метрики за период
GET  /api/analytics/splits          → PreLend split-тесты (splits.json)
PUT  /api/analytics/splits          → обновить splits.json (operator+)
"""

from __future__ import annotations

from typing import Annotated, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator, model_validator

from db.connection import get_db
from services.auth import log_audit, require_operator, require_viewer
from services.config_reader import read_pl_splits
from services.config_writer import write_pl_splits
from services.metrics_collector import (
    collect_funnel,
    _collect_pl_summary,
    _collect_sp_summary,
)

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


# ──────────────────────────────────────────────────────────────────────────────
# Pydantic-схемы splits (зеркалируют структуру SplitTester.php)
# ──────────────────────────────────────────────────────────────────────────────

class SplitVariantSchema(BaseModel):
    """Один вариант A/B теста — совпадает с элементом variants[] в splits.json."""

    id:       str = Field(..., min_length=1, description="Уникальный ID варианта внутри теста")
    template: str = Field(..., min_length=1, description="Имя PHP-шаблона (без расширения)")
    weight:   int = Field(default=1, ge=0, le=1000, description="Вес для weighted random (0 = вариант отключён)")


class SplitSchema(BaseModel):
    """
    Один split-тест — полностью совпадает со структурой, которую читает SplitTester.php.

    Обязательные поля: id, status, variants (≥ 2).
    Остальные — со значениями по умолчанию, совпадающими с PHP-дефолтами.
    """

    id:                   str                                          = Field(..., min_length=1)
    geo:                  List[str]                                    = Field(default_factory=list,
                                                                              description="ISO-2 коды ГЕО; пустой список = все ГЕО")
    status:               Literal["active", "paused", "winner_selected"]
    winner_variant:       Optional[str]                                = Field(default=None, min_length=1)
    min_conversions:      int                                          = Field(default=100, ge=0)
    confidence_threshold: float                                        = Field(default=95.0, ge=0.0, le=100.0)
    variants:             List[SplitVariantSchema]                     = Field(..., min_length=2,
                                                                              description="Минимум 2 варианта для A/B теста")
    decided_at:           Optional[str]                                = Field(
        default=None,
        pattern=r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})?)?$",
        description="ISO-8601, заполняется SplitTester при выборе winner",
    )

    # ── Валидаторы ────────────────────────────────────────────────────────────

    @field_validator("geo", mode="before")
    @classmethod
    def geo_strip(cls, v: list) -> list:
        """Убираем пустые строки и пробелы из гео-списка."""
        if not isinstance(v, list):
            raise ValueError("geo должен быть массивом строк")
        result = []
        for g in v:
            if not isinstance(g, str):
                raise ValueError(f"Элемент гео должен быть строкой, получен: {type(g).__name__}")
            stripped = g.strip().upper()
            if stripped:
                result.append(stripped)
        return result

    @model_validator(mode="after")
    def check_consistency(self) -> "SplitSchema":
        # 1. Уникальность ID вариантов внутри теста
        variant_ids = [v.id for v in self.variants]
        if len(variant_ids) != len(set(variant_ids)):
            duplicates = {vid for vid in variant_ids if variant_ids.count(vid) > 1}
            raise ValueError(f"Дублирующиеся id вариантов: {duplicates}")

        # 2. Сумма весов > 0 (иначе PHP перейдёт в array_rand, что нормально,
        #    но скорее всего означает ошибку конфигурации)
        total_weight = sum(v.weight for v in self.variants)
        if total_weight == 0:
            raise ValueError("Сумма weight по всем вариантам равна 0 — назначьте хотя бы один ненулевой вес")
        # 4. Статус winner_selected требует winner_variant
        if self.status == "winner_selected" and not self.winner_variant:
            raise ValueError("Статус 'winner_selected' требует указания winner_variant")

        # 5. Статус winner_selected требует decided_at
        if self.status == "winner_selected" and self.decided_at is None:
            raise ValueError("Статус 'winner_selected' требует указания decided_at")
            known_ids = {v.id for v in self.variants}
            if self.winner_variant not in known_ids:
                raise ValueError(
                    f"winner_variant='{self.winner_variant}' не найден среди вариантов: {known_ids}"
                )

        # 4. Статус winner_selected требует winner_variant
        if self.status == "winner_selected" and not self.winner_variant:
            raise ValueError("Статус 'winner_selected' требует указания winner_variant")

        return self


def _validate_splits_list(body: List[SplitSchema]) -> None:
    """Проверяет уникальность id тестов на уровне всего списка."""
    ids = [s.id for s in body]
    if len(ids) != len(set(ids)):
        duplicates = {sid for sid in ids if ids.count(sid) > 1}
        raise HTTPException(400, detail=f"Дублирующиеся id тестов: {duplicates}")


# ──────────────────────────────────────────────────────────────────────────────
# Маршруты
# ──────────────────────────────────────────────────────────────────────────────

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


# ──────────────────────────────────────────────────────────────────────────────
# PreLend split-тесты
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/splits")
def get_splits(user: Annotated[dict, Depends(require_viewer)]):
    """Возвращает все split-тесты из PreLend/config/splits.json."""
    return {"splits": read_pl_splits()}


@router.put("/splits")
def update_splits(
    body: List[SplitSchema],
    user: Annotated[dict, Depends(require_operator)],
):
    """
    Перезаписывает PreLend/config/splits.json.

    Тело запроса — JSON-массив объектов, совместимых с SplitTester.php:
      [
        {
          "id": "test_001",
          "status": "active",
          "variants": [
            {"id": "var_a", "template": "expert_review", "weight": 50},
            {"id": "var_b", "template": "sports_news",   "weight": 50}
          ]
        }
      ]

    FastAPI возвращает 422 с подробным описанием при нарушении схемы.
    Дополнительные проверки:
      - вес ≥ 0, сумма весов > 0
      - id вариантов уникальны внутри теста
      - id тестов уникальны в массиве
      - winner_variant ссылается на существующий вариант
      - статус winner_selected требует winner_variant
    """
    if not body:
        raise HTTPException(400, detail="Массив тестов не может быть пустым")

    _validate_splits_list(body)

    # Сериализуем провалидированные модели обратно в dict (совместимый с PHP)
    validated_data = [s.model_dump(exclude_none=True) for s in body]

    write_pl_splits(validated_data, username=user["username"])
    log_audit(
        user, "config_write", "PreLend",
        {"resource": "splits.json", "count": len(body), "ids": [s.id for s in body]},
    )
    return {"success": True, "splits_count": len(body)}
