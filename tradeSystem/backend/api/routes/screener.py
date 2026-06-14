from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from pydantic import BaseModel, Field

from api.deps import require_db
from config.settings import get_settings
from db.repositories import screener as screener_repo
from db.repositories import screener_history as history_repo
from services.basic_screener import run_basic_screen
from services.qlib.catalog import get_factor_expression, list_factor_catalog
from services.qlib.factor_meta import get_factor_info
from services.qlib.screener_service import run_multi_qlib_screen, run_qlib_screen
from services.llm.nl_factor_parser import parse_nl_to_conditions
from services.screener_history_service import save_screen_history

router = APIRouter(prefix="/api/screener", tags=["screener"])


class FactorCondition(BaseModel):
    factor: str = Field(..., description="Alpha158 因子名")
    min_value: float | None = None
    max_value: float | None = None


class SortRule(BaseModel):
    factor: str = Field(..., description="排序因子名")
    order: str = Field("desc", description="asc 升序 / desc 降序")


class MultiScreenRequest(BaseModel):
    conditions: list[FactorCondition]
    market: str = ""
    sector: str = ""
    page: int = Field(1, ge=1)
    page_size: int = Field(50, ge=1, le=200)
    sort: list[SortRule] = Field(default_factory=list, description="多字段排序，优先级从上到下")
    sort_by: str = Field("", description="兼容旧版：单因子降序")


class NlParseRequest(BaseModel):
    text: str = Field(..., min_length=2, max_length=500, description="自然语言选股描述")
    prefer: str = Field("auto", description="auto | llm | rules")


@router.post("/nl-parse")
def parse_nl_conditions(
    body: NlParseRequest,
    _: None = Depends(require_db),
) -> dict[str, Any]:
    prefer = body.prefer.strip().lower()
    if prefer not in ("auto", "llm", "rules"):
        raise HTTPException(400, "prefer 仅支持 auto / llm / rules")
    try:
        return parse_nl_to_conditions(body.text.strip(), get_settings().llm, prefer=prefer)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc


@router.get("/sectors")
def list_sectors(_: None = Depends(require_db)) -> list[str]:
    return screener_repo.list_sectors()


@router.get("/run")
def run_screen(
    market: str = Query("", description="SH / SZ / BJ"),
    sector: str = Query("", description="申万一级行业"),
    min_close: float | None = Query(None, ge=0),
    max_close: float | None = Query(None, ge=0),
    change_days: int = Query(5, ge=1, le=60),
    min_change_pct: float | None = None,
    max_change_pct: float | None = None,
    min_volume: int | None = Query(None, ge=0),
    above_ma: int | None = Query(None, description="收盘价 >= MA(N)，N=5/10/20/60"),
    below_ma: int | None = Query(None, description="收盘价 <= MA(N)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    _: None = Depends(require_db),
) -> dict[str, Any]:
    if above_ma is not None and above_ma not in (5, 10, 20, 60):
        raise HTTPException(400, "above_ma 仅支持 5 / 10 / 20 / 60")
    if below_ma is not None and below_ma not in (5, 10, 20, 60):
        raise HTTPException(400, "below_ma 仅支持 5 / 10 / 20 / 60")
    if above_ma and below_ma:
        raise HTTPException(400, "above_ma 与 below_ma 不可同时设置")

    query = {
        "market": market.strip(),
        "sector": sector.strip(),
        "min_close": min_close,
        "max_close": max_close,
        "change_days": change_days,
        "min_change_pct": min_change_pct,
        "max_change_pct": max_change_pct,
        "min_volume": min_volume,
        "above_ma": above_ma,
        "below_ma": below_ma,
        "page_size": page_size,
    }
    result = run_basic_screen(
        market=query["market"],
        sector=query["sector"],
        min_close=min_close,
        max_close=max_close,
        change_days=change_days,
        min_change_pct=min_change_pct,
        max_change_pct=max_change_pct,
        min_volume=min_volume,
        above_ma=above_ma,
        below_ma=below_ma,
        page=page,
        page_size=page_size,
    )
    history = save_screen_history(mode="basic", query=query, result=result, page=page)
    if history:
        result["history_id"] = history["id"]
    return result


@router.get("/factors")
def list_factors(
    category: str = Query("", description="kbar / momentum / trend / volume …"),
    _: None = Depends(require_db),
) -> dict[str, Any]:
    return list_factor_catalog(category.strip())


@router.get("/factors/{name}")
def get_factor_detail(
    name: str,
    _: None = Depends(require_db),
) -> dict[str, Any]:
    expr = get_factor_expression(name.strip())
    if not expr:
        raise HTTPException(404, f"未知因子: {name}")
    from services.qlib.catalog import _guess_category

    cat = _guess_category(name.strip())
    return get_factor_info(name.strip(), expr, cat)


@router.get("/qlib-run")
def run_qlib_screen_api(
    factor: str = Query(..., description="Alpha158 因子名，如 ROC20、MA5"),
    min_value: float | None = None,
    max_value: float | None = None,
    market: str = Query(""),
    sector: str = Query(""),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    _: None = Depends(require_db),
) -> dict[str, Any]:
    if not factor.strip():
        raise HTTPException(400, "factor 不能为空")
    query = {
        "factor": factor.strip(),
        "min_value": min_value,
        "max_value": max_value,
        "market": market.strip(),
        "sector": sector.strip(),
        "page_size": page_size,
    }
    try:
        result = run_qlib_screen(
            factor=query["factor"],
            min_value=min_value,
            max_value=max_value,
            market=query["market"],
            sector=query["sector"],
            page=page,
            page_size=page_size,
        )
        history = save_screen_history(mode="qlib", query=query, result=result, page=page)
        if history:
            result["history_id"] = history["id"]
        return result
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/multi-run")
def run_multi_screen_api(
    body: MultiScreenRequest,
    _: None = Depends(require_db),
) -> dict[str, Any]:
    try:
        query = {
            "conditions": [c.model_dump(exclude_none=True) for c in body.conditions],
            "market": body.market.strip(),
            "sector": body.sector.strip(),
            "sort": [s.model_dump() for s in body.sort],
            "sort_by": body.sort_by.strip(),
            "page_size": body.page_size,
        }
        result = run_multi_qlib_screen(
            conditions=query["conditions"],
            market=query["market"],
            sector=query["sector"],
            page=body.page,
            page_size=body.page_size,
            sort=query["sort"],
            sort_by=query["sort_by"],
        )
        history = save_screen_history(mode="multi", query=query, result=result, page=body.page)
        if history:
            result["history_id"] = history["id"]
        return result
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/history")
def list_screen_history(
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
    _: None = Depends(require_db),
) -> dict[str, Any]:
    return history_repo.list_history(limit=limit, offset=offset)


@router.get("/history/{entry_id}")
def get_screen_history(
    entry_id: str,
    _: None = Depends(require_db),
) -> dict[str, Any]:
    row = history_repo.get_history(entry_id)
    if not row:
        raise HTTPException(404, "历史记录不存在")
    return row


@router.delete("/history/{entry_id}")
def delete_screen_history(
    entry_id: str,
    _: None = Depends(require_db),
) -> dict[str, Any]:
    if not history_repo.delete_history(entry_id):
        raise HTTPException(404, "历史记录不存在")
    return {"ok": True}


@router.delete("/history")
def clear_screen_history(_: None = Depends(require_db)) -> dict[str, Any]:
    deleted = history_repo.clear_history()
    return {"ok": True, "deleted": deleted}
