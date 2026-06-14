from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from api.deps import require_db
from services.strategy.service import get_catalog, get_strategy, validate_strategy_params

router = APIRouter(prefix="/api/strategy", tags=["strategy"])


class ValidateParamsRequest(BaseModel):
    params: dict[str, Any] = Field(default_factory=dict)


@router.get("/catalog")
def strategy_catalog(
    category: str = Query("", description="按分类筛选"),
    _: None = Depends(require_db),
) -> dict[str, Any]:
    return get_catalog(category=category)


@router.get("/{strategy_id}")
def strategy_detail(
    strategy_id: str,
    _: None = Depends(require_db),
) -> dict[str, Any]:
    try:
        return get_strategy(strategy_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/{strategy_id}/validate")
def strategy_validate_params(
    strategy_id: str,
    body: ValidateParamsRequest,
    _: None = Depends(require_db),
) -> dict[str, Any]:
    try:
        validated = validate_strategy_params(strategy_id, body.params)
        return {"strategy": strategy_id, "params": validated, "valid": True}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
