from __future__ import annotations

from datetime import date, datetime
from typing import Any

from db.connection import get_cursor

DAILY_PERIODS = frozenset({"1d", "1w", "1mon"})
DB_DAILY_PERIOD = frozenset({"1d"})

# numeric 类型的 NaN 在 PG 中满足 `> 0`，查询时需显式排除
_VALID_CLOSE_SQL = (
    "close IS NOT NULL AND close > 0 AND lower(close::text) <> 'nan'"
)
_INVALID_CLOSE_SQL = f"NOT ({_VALID_CLOSE_SQL})"

_OHLC_VIOLATION_SQL = (
    "high < low "
    "OR open < low OR open > high "
    "OR close < low OR close > high"
)


def _cleanup_where(include_ohlc: bool) -> str:
    if include_ohlc:
        return f"({_INVALID_CLOSE_SQL} OR {_OHLC_VIOLATION_SQL})"
    return _INVALID_CLOSE_SQL


def count_invalid_rows(
    *,
    symbol: str | None = None,
    include_ohlc: bool = False,
) -> dict[str, int]:
    where = _cleanup_where(include_ohlc)
    params: list[Any] = []
    symbol_clause = ""
    if symbol:
        symbol_clause = " AND symbol = %s"
        params.append(symbol)

    with get_cursor() as cur:
        cur.execute(
            f"SELECT COUNT(*) AS cnt FROM kline_daily WHERE {where}{symbol_clause}",
            params,
        )
        daily = int(cur.fetchone()["cnt"])
        cur.execute(
            f"SELECT COUNT(*) AS cnt FROM kline_intraday WHERE {where}{symbol_clause}",
            params,
        )
        intraday = int(cur.fetchone()["cnt"])
    return {"kline_daily": daily, "kline_intraday": intraday}


def cleanup_invalid_rows(
    *,
    symbol: str | None = None,
    include_ohlc: bool = False,
    dry_run: bool = True,
) -> dict[str, Any]:
    preview = count_invalid_rows(symbol=symbol, include_ohlc=include_ohlc)
    if dry_run:
        return {
            "dry_run": True,
            "symbol": symbol,
            "include_ohlc": include_ohlc,
            "preview": preview,
            "deleted": {"kline_daily": 0, "kline_intraday": 0},
        }

    where = _cleanup_where(include_ohlc)
    params: list[Any] = []
    symbol_clause = ""
    if symbol:
        symbol_clause = " AND symbol = %s"
        params.append(symbol)

    deleted = {"kline_daily": 0, "kline_intraday": 0}
    with get_cursor() as cur:
        cur.execute(
            f"DELETE FROM kline_daily WHERE {where}{symbol_clause}",
            params,
        )
        deleted["kline_daily"] = cur.rowcount
        cur.execute(
            f"DELETE FROM kline_intraday WHERE {where}{symbol_clause}",
            params,
        )
        deleted["kline_intraday"] = cur.rowcount

    return {
        "dry_run": False,
        "symbol": symbol,
        "include_ohlc": include_ohlc,
        "preview": preview,
        "deleted": deleted,
    }


def count_kline_rows() -> int:
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM kline_daily)
              + (SELECT COUNT(*) FROM kline_intraday) AS cnt
            """,
        )
        row = cur.fetchone()
        return int(row["cnt"]) if row else 0


def upsert_daily_rows(rows: list[tuple]) -> int:
    if not rows:
        return 0
    with get_cursor() as cur:
        cur.executemany(
            """
            INSERT INTO kline_daily
                (symbol, trade_date, open, high, low, close, volume, amount)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (symbol, trade_date) DO UPDATE SET
                open = EXCLUDED.open,
                high = EXCLUDED.high,
                low = EXCLUDED.low,
                close = EXCLUDED.close,
                volume = EXCLUDED.volume,
                amount = EXCLUDED.amount
            """,
            rows,
        )
    return len(rows)


def upsert_intraday_rows(rows: list[tuple]) -> int:
    if not rows:
        return 0
    with get_cursor() as cur:
        cur.executemany(
            """
            INSERT INTO kline_intraday
                (symbol, period, bar_time, open, high, low, close, volume, amount)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (symbol, period, bar_time) DO UPDATE SET
                open = EXCLUDED.open,
                high = EXCLUDED.high,
                low = EXCLUDED.low,
                close = EXCLUDED.close,
                volume = EXCLUDED.volume,
                amount = EXCLUDED.amount
            """,
            rows,
        )
    return len(rows)


def query_daily(
    symbol: str,
    limit: int = 30,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[dict[str, Any]]:
    conditions = ["symbol = %s", _VALID_CLOSE_SQL]
    params: list[Any] = [symbol]
    if start_date:
        conditions.append("trade_date >= %s")
        params.append(start_date)
    if end_date:
        conditions.append("trade_date <= %s")
        params.append(end_date)

    where = " AND ".join(conditions)
    with get_cursor() as cur:
        cur.execute(
            f"""
            SELECT trade_date, open, high, low, close, volume, amount
            FROM kline_daily
            WHERE {where}
            ORDER BY trade_date DESC
            LIMIT %s
            """,
            [*params, limit],
        )
        rows = []
        for r in cur.fetchall():
            rows.append(
                {
                    "date": r["trade_date"].isoformat(),
                    "open": float(r["open"]),
                    "high": float(r["high"]),
                    "low": float(r["low"]),
                    "close": float(r["close"]),
                    "volume": int(r["volume"]),
                    "amount": float(r["amount"]),
                },
            )
        rows.reverse()
        return rows


def query_daily_range(
    symbol: str,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[dict[str, Any]]:
    """按日期范围查询日 K（升序，无条数上限），供回测使用。"""
    conditions = ["symbol = %s", _VALID_CLOSE_SQL]
    params: list[Any] = [symbol]
    if start_date:
        conditions.append("trade_date >= %s")
        params.append(start_date)
    if end_date:
        conditions.append("trade_date <= %s")
        params.append(end_date)

    where = " AND ".join(conditions)
    with get_cursor() as cur:
        cur.execute(
            f"""
            SELECT trade_date, open, high, low, close, volume, amount
            FROM kline_daily
            WHERE {where}
            ORDER BY trade_date ASC
            """,
            params,
        )
        rows = []
        for r in cur.fetchall():
            rows.append(
                {
                    "date": r["trade_date"].isoformat(),
                    "open": float(r["open"]),
                    "high": float(r["high"]),
                    "low": float(r["low"]),
                    "close": float(r["close"]),
                    "volume": int(r["volume"]),
                    "amount": float(r["amount"]),
                },
            )
        return rows


def query_intraday(
    symbol: str,
    period: str,
    limit: int = 30,
) -> list[dict[str, Any]]:
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT bar_time, open, high, low, close, volume, amount
            FROM kline_intraday
            WHERE symbol = %s AND period = %s AND """
            + _VALID_CLOSE_SQL
            + """
            ORDER BY bar_time DESC
            LIMIT %s
            """,
            (symbol, period, limit),
        )
        rows = []
        for r in cur.fetchall():
            bt: datetime = r["bar_time"]
            rows.append(
                {
                    "date": bt.strftime("%Y-%m-%d %H:%M:%S"),
                    "open": float(r["open"]),
                    "high": float(r["high"]),
                    "low": float(r["low"]),
                    "close": float(r["close"]),
                    "volume": int(r["volume"]),
                    "amount": float(r["amount"]),
                },
            )
        rows.reverse()
        return rows


KNOWN_TABLES = frozenset({
    "symbols",
    "kline_daily",
    "kline_intraday",
    "sync_jobs",
    "sync_logs",
    "app_settings",
    "screener_history",
})


def _table_comment(cur, name: str) -> str:
    cur.execute(
        """
        SELECT COALESCE(obj_description(c.oid), '') AS desc
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relname = %s AND c.relkind = 'r'
        """,
        (name,),
    )
    row = cur.fetchone()
    return str(row["desc"] or "") if row else ""


def table_stats() -> list[dict[str, Any]]:
    specs = [
        ("symbols", "SELECT MAX(updated_at) FROM symbols"),
        ("kline_daily", "SELECT MAX(trade_date)::timestamptz FROM kline_daily"),
        ("kline_intraday", "SELECT MAX(bar_time) FROM kline_intraday"),
        ("sync_jobs", "SELECT MAX(created_at) FROM sync_jobs"),
        ("sync_logs", "SELECT MAX(created_at) FROM sync_logs"),
        ("app_settings", "SELECT MAX(updated_at) FROM app_settings"),
        ("screener_history", "SELECT MAX(created_at) FROM screener_history"),
    ]
    result: list[dict[str, Any]] = []
    with get_cursor() as cur:
        for name, lu_sql in specs:
            cur.execute(f"SELECT COUNT(*) AS cnt FROM {name}")
            cnt = int(cur.fetchone()["cnt"])
            cur.execute(
                "SELECT pg_total_relation_size(%s::regclass) AS bytes",
                (name,),
            )
            bytes_size = int(cur.fetchone()["bytes"] or 0)
            cur.execute(f"SELECT ({lu_sql}) AS lu")
            lu_row = cur.fetchone()
            lu = lu_row["lu"] if lu_row else None
            last_updated = lu.isoformat() if lu else None
            description = _table_comment(cur, name)
            result.append(
                {
                    "name": name,
                    "rows": cnt,
                    "size_mb": round(bytes_size / 1024 / 1024, 2),
                    "last_updated": last_updated,
                    "description": description,
                },
            )
    return result


def list_table_columns(table: str) -> list[dict[str, Any]]:
    if table not in KNOWN_TABLES:
        return []
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT
                a.attname AS name,
                pg_catalog.format_type(a.atttypid, a.atttypmod) AS type,
                NOT a.attnotnull AS nullable,
                COALESCE(col_description(a.attrelid, a.attnum), '') AS description
            FROM pg_attribute a
            JOIN pg_class c ON c.oid = a.attrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public'
              AND c.relname = %s
              AND c.relkind = 'r'
              AND a.attnum > 0
              AND NOT a.attisdropped
            ORDER BY a.attnum
            """,
            (table,),
        )
        return [
            {
                "name": r["name"],
                "type": r["type"],
                "nullable": bool(r["nullable"]),
                "description": r["description"] or "",
            }
            for r in cur.fetchall()
        ]
