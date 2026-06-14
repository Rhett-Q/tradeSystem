from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_WORKSPACE = Path(__file__).resolve().parents[3]
if str(_WORKSPACE) not in sys.path:
    sys.path.insert(0, str(_WORKSPACE))

from minqmt.symbols import normalize_symbol, to_xt_symbol

from db.repositories import kline as kline_repo
from db.repositories import symbols as symbol_repo
from db.repositories.kline import DAILY_PERIODS, DB_DAILY_PERIOD
from services.kline_resample import RESAMPLE_FROM_DAILY, daily_fetch_limit, resample_daily_rows
from services.sync_engine import get_sync_engine


def _rows_from_minqmt_daily(bare: str, daily_limit: int) -> list[dict[str, Any]]:
    engine = get_sync_engine()
    if not engine.is_minqmt_connected():
        return []

    df = engine.fetcher.get_kline([bare], period="1d", count=daily_limit)  # type: ignore[arg-type]
    if df.empty:
        return []

    from services.time_utils import parse_trade_date

    rows: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        t = row["time"]
        rows.append(
            {
                "date": parse_trade_date(t).isoformat(),
                "open": float(row.get("open", 0)),
                "high": float(row.get("high", 0)),
                "low": float(row.get("low", 0)),
                "close": float(row.get("close", 0)),
                "volume": int(row.get("volume", 0) or 0),
                "amount": float(row.get("amount", 0) or 0),
            },
        )
    return rows


def _get_resampled_kline(xt_symbol: str, period: str, limit: int) -> tuple[list[dict[str, Any]], str]:
    daily_limit = daily_fetch_limit(period, limit)
    daily_rows = kline_repo.query_daily(xt_symbol, limit=daily_limit)
    source = "resampled"

    if not daily_rows:
        bare = normalize_symbol(xt_symbol)
        daily_rows = _rows_from_minqmt_daily(bare, daily_limit)
        source = "minqmt_resampled"

    if not daily_rows:
        return [], "none"

    resampled = resample_daily_rows(daily_rows, period)
    if limit > 0 and len(resampled) > limit:
        resampled = resampled[-limit:]
    return resampled, source


def _attach_symbol_meta(payload: dict[str, Any]) -> dict[str, Any]:
    meta = symbol_repo.get_symbol(payload["symbol"])
    payload["name"] = (meta or {}).get("name") or ""
    payload["sector"] = (meta or {}).get("sector") or ""
    return payload


def get_kline(symbol: str, period: str = "1d", limit: int = 30) -> dict[str, Any]:
    xt_symbol = to_xt_symbol(symbol)

    if period in RESAMPLE_FROM_DAILY:
        rows, source = _get_resampled_kline(xt_symbol, period, limit)
        return _attach_symbol_meta(
            {"symbol": xt_symbol, "period": period, "rows": rows, "source": source},
        )

    if period in DB_DAILY_PERIOD:
        rows = kline_repo.query_daily(xt_symbol, limit=limit)
    else:
        rows = kline_repo.query_intraday(xt_symbol, period, limit=limit)

    if rows:
        return _attach_symbol_meta(
            {"symbol": xt_symbol, "period": period, "rows": rows, "source": "database"},
        )

    engine = get_sync_engine()
    if not engine.is_minqmt_connected():
        return _attach_symbol_meta(
            {"symbol": xt_symbol, "period": period, "rows": [], "source": "none"},
        )

    bare = normalize_symbol(symbol)
    df = engine.fetcher.get_kline([bare], period=period, count=limit)  # type: ignore[arg-type]
    if df.empty:
        return _attach_symbol_meta(
            {"symbol": xt_symbol, "period": period, "rows": [], "source": "minqmt"},
        )

    rows = []
    for _, row in df.tail(limit).iterrows():
        t = row["time"]
        if period in DAILY_PERIODS:
            from services.time_utils import parse_trade_date
            date_str = parse_trade_date(t).isoformat()
        else:
            from services.time_utils import parse_bar_datetime
            date_str = parse_bar_datetime(t).strftime("%Y-%m-%d %H:%M:%S")
        rows.append(
            {
                "date": date_str,
                "open": float(row.get("open", 0)),
                "high": float(row.get("high", 0)),
                "low": float(row.get("low", 0)),
                "close": float(row.get("close", 0)),
                "volume": int(row.get("volume", 0) or 0),
                "amount": float(row.get("amount", 0) or 0),
            },
        )
    return _attach_symbol_meta(
        {"symbol": xt_symbol, "period": period, "rows": rows, "source": "minqmt"},
    )

