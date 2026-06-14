from __future__ import annotations

import math
from typing import Any

from db.connection import get_cursor
from services.screener_filters import listed_symbol_where

# numeric 类型的 NaN 在 PG 中满足 `> 0`，需显式排除
_VALID_CLOSE = (
    "k.close IS NOT NULL AND k.close > 0 AND lower(k.close::text) <> 'nan'"
)


def list_sectors() -> list[str]:
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT sector
            FROM symbols
            WHERE sector IS NOT NULL AND sector <> ''
            ORDER BY sector
            """,
        )
        return [str(r["sector"]) for r in cur.fetchall()]


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(num) or math.isinf(num):
        return None
    return num


def _safe_int(value: Any) -> int:
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def screen(
    *,
    market: str = "",
    sector: str = "",
    min_close: float | None = None,
    max_close: float | None = None,
    change_days: int = 5,
    min_change_pct: float | None = None,
    max_change_pct: float | None = None,
    min_volume: int | None = None,
    above_ma: int | None = None,
    below_ma: int | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    change_days = max(1, min(change_days, 60))
    ma_period = above_ma or below_ma or 0
    lookback = max(change_days + 1, ma_period, 2)
    # 日历日窗口，覆盖足够交易日（含长假）
    calendar_days = max(lookback * 3, 90)
    offset = (page - 1) * page_size

    symbol_conds = [listed_symbol_where("s")]
    params: list[Any] = []

    if market:
        symbol_conds.append("s.market = %s")
        params.append(market.upper())
    if sector:
        symbol_conds.append("s.sector = %s")
        params.append(sector)

    symbol_where = " AND ".join(symbol_conds)
    filters: list[str] = []
    filter_params: list[Any] = []

    if min_close is not None:
        filters.append("l.close >= %s")
        filter_params.append(min_close)
    if max_close is not None:
        filters.append("l.close <= %s")
        filter_params.append(max_close)
    if min_volume is not None:
        filters.append("l.volume >= %s")
        filter_params.append(min_volume)
    if min_change_pct is not None:
        filters.append(
            "b.base_close > 0 AND (l.close - b.base_close) / b.base_close * 100 >= %s",
        )
        filter_params.append(min_change_pct)
    if max_change_pct is not None:
        filters.append(
            "b.base_close > 0 AND (l.close - b.base_close) / b.base_close * 100 <= %s",
        )
        filter_params.append(max_change_pct)
    if above_ma:
        filters.append("m.ma_value IS NOT NULL AND l.close >= m.ma_value")
    if below_ma:
        filters.append("m.ma_value IS NOT NULL AND l.close <= m.ma_value")

    filter_sql = ""
    if filters:
        filter_sql = " AND " + " AND ".join(filters)

    base_rn = change_days + 1
    ma_need = ma_period if ma_period else 1

    select_body = f"""
        WITH universe AS (
            SELECT s.symbol
            FROM symbols s
            WHERE {symbol_where}
        ),
        last_dates AS (
            SELECT k.symbol, MAX(k.trade_date) AS last_date
            FROM kline_daily k
            INNER JOIN universe u ON u.symbol = k.symbol
            WHERE {_VALID_CLOSE}
            GROUP BY k.symbol
        ),
        recent AS (
            SELECT
                k.symbol,
                k.trade_date,
                k.close,
                k.volume,
                k.amount,
                ROW_NUMBER() OVER (PARTITION BY k.symbol ORDER BY k.trade_date DESC) AS rn
            FROM kline_daily k
            INNER JOIN last_dates ld ON ld.symbol = k.symbol
            WHERE k.trade_date >= ld.last_date - %s * INTERVAL '1 day'
              AND {_VALID_CLOSE}
        ),
        last_bar AS (
            SELECT symbol, trade_date, close, volume, amount
            FROM recent WHERE rn = 1
        ),
        base_bar AS (
            SELECT symbol, close AS base_close
            FROM recent WHERE rn = %s
        ),
        ma_bar AS (
            SELECT symbol, AVG(close) AS ma_value
            FROM recent
            WHERE rn <= %s
            GROUP BY symbol
            HAVING COUNT(*) >= %s
        )
        SELECT
            s.symbol,
            s.name,
            s.market,
            s.sector,
            l.trade_date,
            l.close,
            l.volume,
            l.amount,
            CASE
                WHEN b.base_close > 0
                THEN ROUND(((l.close - b.base_close) / b.base_close * 100)::numeric, 2)
                ELSE NULL
            END AS change_pct,
            CASE WHEN m.ma_value IS NOT NULL THEN ROUND(m.ma_value::numeric, 4) ELSE NULL END AS ma_value
        FROM last_bar l
        JOIN symbols s ON s.symbol = l.symbol
        LEFT JOIN base_bar b ON b.symbol = l.symbol
        LEFT JOIN ma_bar m ON m.symbol = l.symbol
        WHERE 1=1{filter_sql}
    """

    cte_params = [*params, calendar_days, base_rn, ma_need, ma_need]

    with get_cursor() as cur:
        cur.execute(
            f"SELECT COUNT(*) AS cnt FROM ({select_body}) q",
            [*cte_params, *filter_params],
        )
        total = int(cur.fetchone()["cnt"])

        cur.execute(
            select_body
            + """
            ORDER BY change_pct DESC NULLS LAST, s.symbol
            LIMIT %s OFFSET %s
            """,
            [*cte_params, *filter_params, page_size, offset],
        )
        rows = []
        for r in cur.fetchall():
            close = _safe_float(r["close"])
            if close is None:
                continue
            rows.append(
                {
                    "symbol": r["symbol"],
                    "name": r["name"],
                    "market": r["market"],
                    "sector": r["sector"],
                    "trade_date": r["trade_date"].isoformat() if r["trade_date"] else None,
                    "close": close,
                    "volume": _safe_int(r["volume"]),
                    "amount": _safe_float(r["amount"]) or 0.0,
                    "change_pct": _safe_float(r["change_pct"]),
                    "ma_value": _safe_float(r["ma_value"]),
                },
            )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "change_days": change_days,
        "above_ma": above_ma,
        "below_ma": below_ma,
        "rows": rows,
    }
