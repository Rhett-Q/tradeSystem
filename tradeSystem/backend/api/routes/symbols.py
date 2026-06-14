from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import get_engine, require_db
from db.repositories import symbols as symbol_repo
from services.sync_engine import SyncEngine

router = APIRouter(prefix="/api/symbols", tags=["symbols"])


@router.get("")
def list_symbols(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str = "",
    market: str = "",
    _: None = Depends(require_db),
) -> dict[str, Any]:
    return symbol_repo.list_symbols(page, page_size, keyword, market)


@router.get("/search")
def search_symbols(
    q: str = Query("", min_length=1),
    limit: int = Query(10, ge=1, le=50),
    _: None = Depends(require_db),
) -> list[dict[str, Any]]:
    return symbol_repo.search_symbols(q, limit)


@router.post("/refresh")
def refresh_symbols(
    engine: SyncEngine = Depends(get_engine),
    _: None = Depends(require_db),
) -> dict[str, Any]:
    try:
        count = engine.refresh_universe_to_db()
    except ConnectionError as exc:
        raise HTTPException(503, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(503, str(exc)) from exc
    return {"count": count, "message": f"已刷新 {count} 只标的"}
