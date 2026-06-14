from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from services.market_service import get_kline

router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("/kline")
def kline(
    symbol: str = Query("600519.SH"),
    period: str = Query("1d"),
    limit: int = Query(30, ge=1, le=500),
) -> dict[str, Any]:
    return get_kline(symbol, period, limit)
