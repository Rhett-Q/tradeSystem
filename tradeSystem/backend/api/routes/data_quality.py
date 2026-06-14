from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from api.deps import require_db
from db.repositories import data_quality as quality_repo
from db.repositories import kline as kline_repo
from minqmt.symbols import to_xt_symbol

router = APIRouter(prefix="/api/quality", tags=["quality"])


class CleanupRequest(BaseModel):
    symbol: Optional[str] = Field(None, description="仅清理指定标的，留空则全库")
    include_ohlc: bool = Field(False, description="同时清理 OHLC 逻辑异常行")
    dry_run: bool = Field(True, description="true=仅预览将删除的数量，false=执行删除")


@router.get("/summary")
def quality_summary(
    stale_days: int = Query(5, ge=1, le=60, description="判定行情滞后的天数阈值"),
    _: None = Depends(require_db),
) -> dict[str, Any]:
    summary = quality_repo.get_summary(stale_days=stale_days)
    breakdown = quality_repo.get_issue_breakdown(stale_days=stale_days)
    return {"summary": summary, "breakdown": breakdown}


@router.get("/issues")
def quality_issues(
    issue_type: str = Query("stale", description="问题类型"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    stale_days: int = Query(5, ge=1, le=60),
    _: None = Depends(require_db),
) -> dict[str, Any]:
    return quality_repo.list_issues(
        issue_type=issue_type,
        page=page,
        page_size=page_size,
        stale_days=stale_days,
    )


@router.get("/cleanup/preview")
def cleanup_preview(
    symbol: str | None = Query(None, description="指定标的，如 001393.SZ"),
    include_ohlc: bool = Query(False),
    _: None = Depends(require_db),
) -> dict[str, Any]:
    try:
        xt_symbol = to_xt_symbol(symbol) if symbol else None
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    preview = kline_repo.count_invalid_rows(symbol=xt_symbol, include_ohlc=include_ohlc)
    return {
        "symbol": xt_symbol,
        "include_ohlc": include_ohlc,
        "preview": preview,
        "total": preview["kline_daily"] + preview["kline_intraday"],
    }


@router.post("/cleanup")
def cleanup_invalid_klines(
    body: CleanupRequest,
    _: None = Depends(require_db),
) -> dict[str, Any]:
    try:
        xt_symbol = to_xt_symbol(body.symbol) if body.symbol else None
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return kline_repo.cleanup_invalid_rows(
        symbol=xt_symbol,
        include_ohlc=body.include_ohlc,
        dry_run=body.dry_run,
    )
