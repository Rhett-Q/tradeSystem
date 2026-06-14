from __future__ import annotations

from pathlib import Path
from typing import Any, List, Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from minqmt.filter_expr import FilterExprError, validate_filter_expr
from web.deps import get_state
from web.serializers import to_json
from web.state import AppState

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="MiniQMT Quant Dashboard", version="1.0.0")


# ── request models ──


class FilterCreate(BaseModel):
    name: str
    expr: str
    description: str = ""
    enabled: bool = True


class FilterUpdate(BaseModel):
    name: Optional[str] = None
    expr: Optional[str] = None
    description: Optional[str] = None
    enabled: Optional[bool] = None


class FilterToggle(BaseModel):
    enabled: bool


class ExprValidate(BaseModel):
    expr: str


class SyncFullRequest(BaseModel):
    start: str = "20200101"
    period: str = "1d"
    batch_size: int = 200


class SyncIncrementalRequest(BaseModel):
    period: str = "1d"
    batch_size: int = 300


class ScreenRequest(BaseModel):
    source: str = "universe"
    node_id: str = "hs300"
    bar_count: int = 21
    max_stocks: Optional[int] = Field(default=500, le=5000)


class WatchAddRequest(BaseModel):
    symbols: List[str] = Field(default_factory=list)


class PromoteRequest(BaseModel):
    symbols: List[str]
    target_node: str = "trade_momentum"


# ── health ──


@app.get("/api/health")
def health(state: AppState = Depends(get_state)) -> dict[str, Any]:
    universe_size = None
    error = ""
    connected = False
    try:
        connected = state.is_connected()
        if connected:
            universe_size = len(state.sync.get_universe())
    except Exception as exc:
        error = str(exc)
    return {
        "connected": connected,
        "universe_size": universe_size,
        "error": error,
    }


# ── sync ──


@app.get("/api/sync/status")
def sync_status(state: AppState = Depends(get_state)) -> dict[str, Any]:
    job = state.sync_job
    if not job:
        return {"status": "idle"}
    return to_json(job)


@app.get("/api/sync/universe")
def sync_universe(state: AppState = Depends(get_state)) -> dict[str, Any]:
    try:
        codes = state.sync.get_universe()
    except Exception as exc:
        raise HTTPException(503, str(exc)) from exc
    return {"count": len(codes), "sample": codes[:30]}


@app.post("/api/sync/full")
def sync_full(
    body: SyncFullRequest,
    state: AppState = Depends(get_state),
) -> dict[str, Any]:
    try:
        job = state.start_sync(
            "full",
            start_time=body.start,
            period=body.period,
            batch_size=body.batch_size,
        )
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    return to_json(job)


@app.post("/api/sync/incremental")
def sync_incremental(
    body: SyncIncrementalRequest,
    state: AppState = Depends(get_state),
) -> dict[str, Any]:
    try:
        job = state.start_sync(
            "incremental",
            period=body.period,
            batch_size=body.batch_size,
        )
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    return to_json(job)


# ── filters / screen ──


@app.get("/api/filters")
def list_filters(state: AppState = Depends(get_state)) -> list[dict[str, Any]]:
    return [f.to_dict() for f in state.screener.list_filters()]


@app.get("/api/filters/fields")
def filter_fields(state: AppState = Depends(get_state)) -> dict[str, str]:
    return state.screener.available_fields()


@app.post("/api/filters/validate")
def validate_expr(body: ExprValidate) -> dict[str, Any]:
    ok, msg = validate_filter_expr(body.expr)
    return {"ok": ok, "message": msg}


@app.post("/api/filters")
def create_filter(
    body: FilterCreate,
    state: AppState = Depends(get_state),
) -> dict[str, Any]:
    try:
        rule = state.screener.add_custom_filter(
            body.name, body.expr, body.description, enabled=body.enabled
        )
        state.save()
        return rule.to_dict()
    except FilterExprError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.put("/api/filters/{filter_id}")
def update_filter(
    filter_id: str,
    body: FilterUpdate,
    state: AppState = Depends(get_state),
) -> dict[str, Any]:
    try:
        rule = state.screener.update_filter(
            filter_id,
            name=body.name,
            expr=body.expr,
            description=body.description,
            enabled=body.enabled,
        )
        state.save()
        return rule.to_dict()
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except FilterExprError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.patch("/api/filters/{filter_id}/enabled")
def toggle_filter(
    filter_id: str,
    body: FilterToggle,
    state: AppState = Depends(get_state),
) -> dict[str, Any]:
    rule = state.screener.get_filter(filter_id)
    if not rule:
        raise HTTPException(404, "规则不存在")
    state.screener.set_filter_enabled(filter_id, body.enabled)
    state.save()
    rule = state.screener.get_filter(filter_id)
    return rule.to_dict() if rule else {}


@app.delete("/api/filters/{filter_id}")
def delete_filter(
    filter_id: str,
    state: AppState = Depends(get_state),
) -> dict[str, str]:
    try:
        state.screener.remove_filter(filter_id)
        state.save()
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except FilterExprError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"ok": "deleted"}


@app.get("/api/triggers")
def list_triggers(state: AppState = Depends(get_state)) -> list[dict[str, Any]]:
    return [to_json(t) for t in state.screener.triggers]


@app.post("/api/screen")
def run_screen(
    body: ScreenRequest,
    state: AppState = Depends(get_state),
) -> dict[str, Any]:
    try:
        if body.source == "node":
            pool_df = state.pools.build_from_node(
                body.node_id,
                bar_count=body.bar_count,
                max_stocks=body.max_stocks,
            )
            universe = pool_df["symbol"].astype(str).tolist() if not pool_df.empty else []
        else:
            universe = state.sync.get_universe()
            if body.max_stocks:
                universe = universe[: body.max_stocks]

        result = state.screener.run_screen(universe, bar_count=body.bar_count)
    except Exception as exc:
        raise HTTPException(503, str(exc)) from exc

    return {
        "count": len(result),
        "rows": to_json(result),
    }


# ── watchlist ──


@app.get("/api/watchlist")
def get_watchlist(state: AppState = Depends(get_state)) -> list[dict[str, Any]]:
    return [to_json(w) for w in state.watchlist]


@app.post("/api/watchlist/refresh")
def refresh_watchlist(state: AppState = Depends(get_state)) -> list[dict[str, Any]]:
    return [to_json(w) for w in state.refresh_watchlist()]


@app.post("/api/watchlist")
def add_watchlist(
    body: WatchAddRequest,
    state: AppState = Depends(get_state),
) -> list[dict[str, Any]]:
    if not body.symbols:
        raise HTTPException(400, "symbols 不能为空")
    try:
        universe = state.sync.get_universe()
        df = state.screener.run_screen(universe[:2000], bar_count=21)
        rows = df[df["symbol"].astype(str).isin(body.symbols)].to_dict(orient="records")
        if not rows:
            rows = [{"symbol": s, "name": s} for s in body.symbols]
        items = state.add_to_watchlist(rows)
    except Exception as exc:
        raise HTTPException(503, str(exc)) from exc
    return [to_json(w) for w in items]


@app.delete("/api/watchlist/{symbol}")
def remove_watchlist(
    symbol: str,
    state: AppState = Depends(get_state),
) -> dict[str, str]:
    state.remove_watch(symbol)
    return {"ok": "removed"}


# ── pools ──


@app.get("/api/pools/hierarchy")
def pool_hierarchy(state: AppState = Depends(get_state)) -> list[dict[str, Any]]:
    return state.pools.list_hierarchy()


@app.get("/api/pools/{node_id}")
def build_pool(
    node_id: str,
    bar_count: int = 21,
    max_stocks: Optional[int] = 100,
    state: AppState = Depends(get_state),
) -> dict[str, Any]:
    try:
        df = state.pools.build_from_node(
            node_id, bar_count=bar_count, max_stocks=max_stocks
        )
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(503, str(exc)) from exc
    return {
        "node_id": node_id,
        "path": state.pools.get_pool_path(node_id),
        "count": len(df),
        "rows": to_json(df),
    }


@app.post("/api/pools/promote")
def promote_pool(
    body: PromoteRequest,
    state: AppState = Depends(get_state),
) -> dict[str, Any]:
    promoted = state.pools.promote_to_tradable(body.symbols, body.target_node)
    return {"promoted": promoted, "target_node": body.target_node}


# ── static UI ──


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
