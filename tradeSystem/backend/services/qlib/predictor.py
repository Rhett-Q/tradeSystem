from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from db.connection import get_cursor
from services.qlib.catalog import get_factor_expression
from services.qlib.expression import evaluate_expression, required_lookback
from services.qlib.panel import get_panel, iter_symbol_frames
from services.qlib.trainer import get_model_meta, load_model
from services.screener_filters import listed_symbol_where


def _load_symbol_meta(market: str, sector: str) -> dict[str, dict[str, Any]]:
    conds = [listed_symbol_where()]
    params: list[Any] = []
    if market:
        conds.append("market = %s")
        params.append(market.upper())
    if sector:
        conds.append("sector = %s")
        params.append(sector)
    where = " AND ".join(conds)
    with get_cursor() as cur:
        cur.execute(
            f"SELECT symbol, name, market, sector FROM symbols WHERE {where}",
            params,
        )
        return {r["symbol"]: dict(r) for r in cur.fetchall()}


def predict_universe(
    *,
    model_id: str,
    market: str = "",
    sector: str = "",
    top_n: int = 50,
) -> dict[str, Any]:
    meta = get_model_meta(model_id)
    if not meta:
        raise ValueError(f"模型不存在: {model_id}")

    model = load_model(model_id)
    factors: list[str] = meta["factors"]
    library = meta["library_id"]
    expressions = {name: get_factor_expression(name, library) for name in factors}
    if any(v is None for v in expressions.values()):
        raise ValueError("模型因子与当前因子库不匹配")

    lookback = max(required_lookback(expr) for expr in expressions.values() if expr) + 10
    panel = get_panel(lookback)
    if panel.empty:
        raise ValueError("无日 K 数据，请先同步日线")

    universe = _load_symbol_meta(market, sector)
    rows: list[dict[str, Any]] = []

    for symbol, frame in iter_symbol_frames(panel):
        if symbol not in universe:
            continue
        feat: dict[str, float] = {}
        ok = True
        for name, expr in expressions.items():
            if not expr:
                ok = False
                break
            try:
                series = evaluate_expression(expr, frame)
                val = series.iloc[-1]
                if val is None or (isinstance(val, float) and (math.isnan(val) or math.isinf(val))):
                    ok = False
                    break
                feat[name] = float(val)
            except ValueError:
                ok = False
                break
        if not ok:
            continue

        x = pd.DataFrame([feat])
        score = float(model.predict(x)[0])
        last = frame.iloc[-1]
        trade_date = frame.index[-1]
        info = universe[symbol]
        rows.append({
            "symbol": symbol,
            "name": info.get("name") or "",
            "market": info.get("market") or "",
            "sector": info.get("sector"),
            "score": round(score, 6),
            "close": float(last["close"]) if last.get("close") is not None else None,
            "trade_date": trade_date.strftime("%Y-%m-%d")
            if hasattr(trade_date, "strftime")
            else str(trade_date)[:10],
        })

    rows.sort(key=lambda r: r["score"], reverse=True)
    top = rows[:top_n]

    return {
        "model_id": model_id,
        "model_meta": meta,
        "total": len(rows),
        "top_n": top_n,
        "rows": top,
    }
