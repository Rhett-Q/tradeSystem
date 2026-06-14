from __future__ import annotations

from datetime import date, datetime
from typing import Any

from db.connection import get_cursor

# numeric 类型的 NaN 在 PG 中满足 `> 0`，需显式排除
_INVALID_CLOSE = (
    "close IS NULL OR close <= 0 OR lower(close::text) = 'nan'"
)

_OHLC_VIOLATION = (
    "high < low "
    "OR open < low OR open > high "
    "OR close < low OR close > high"
)


def _serialize(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _row_dict(row: dict[str, Any]) -> dict[str, Any]:
    return {k: _serialize(v) for k, v in dict(row).items()}


def get_summary(*, stale_days: int = 5) -> dict[str, Any]:
    stale_days = max(1, min(stale_days, 60))
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM symbols WHERE is_listed = TRUE) AS listed_count,
                (SELECT COUNT(*) FROM symbols) AS symbol_total,
                (SELECT COUNT(DISTINCT symbol) FROM kline_daily) AS symbols_with_daily,
                (SELECT COUNT(*) FROM kline_daily) AS daily_rows,
                (SELECT MAX(trade_date) FROM kline_daily) AS latest_daily_date,
                (SELECT COUNT(*) FROM kline_daily WHERE """
            + _INVALID_CLOSE
            + """) AS invalid_close_rows,
                (SELECT COUNT(*) FROM kline_daily WHERE """
            + _OHLC_VIOLATION
            + """) AS ohlc_violation_rows,
                (SELECT COUNT(*) FROM kline_daily WHERE volume = 0) AS zero_volume_rows,
                (SELECT COUNT(DISTINCT k.symbol) FROM kline_daily k
                 WHERE NOT EXISTS (
                     SELECT 1 FROM symbols s WHERE s.symbol = k.symbol
                 )) AS orphan_symbols,
                (SELECT COUNT(*) FROM symbols s
                 WHERE s.is_listed = TRUE
                   AND NOT EXISTS (
                       SELECT 1 FROM kline_daily k WHERE k.symbol = s.symbol
                   )) AS listed_no_kline,
                (SELECT COUNT(*) FROM symbols
                 WHERE is_listed = TRUE
                   AND (name IS NULL OR name = ''
                        OR sector IS NULL OR sector = '')) AS missing_metadata,
                (SELECT COUNT(*) FROM sync_jobs
                 WHERE status = 'failed'
                   AND created_at > NOW() - INTERVAL '7 days') AS failed_jobs_7d,
                (SELECT COUNT(*) FROM sync_logs
                 WHERE level = 'error'
                   AND created_at > NOW() - INTERVAL '7 days') AS error_logs_7d,
                (SELECT COUNT(*) FROM sync_logs
                 WHERE level = 'warn'
                   AND created_at > NOW() - INTERVAL '7 days') AS warn_logs_7d
            """
        )
        base = _row_dict(cur.fetchone())

        latest = base.get("latest_daily_date")
        stale_count = 0
        if latest:
            cur.execute(
                """
                WITH latest AS (SELECT %s::date AS max_date)
                SELECT COUNT(*) AS cnt
                FROM symbols s
                WHERE s.is_listed = TRUE
                  AND (
                      NOT EXISTS (
                          SELECT 1 FROM kline_daily k WHERE k.symbol = s.symbol
                      )
                      OR (
                          SELECT MAX(k.trade_date) FROM kline_daily k
                          WHERE k.symbol = s.symbol
                      ) < (SELECT max_date FROM latest) - %s * INTERVAL '1 day'
                  )
                """,
                (latest, stale_days),
            )
            stale_count = int(cur.fetchone()["cnt"])

        listed = int(base.get("listed_count") or 0)
        with_daily = int(base.get("symbols_with_daily") or 0)
        coverage_pct = round(with_daily / listed * 100, 1) if listed else 0.0

        cur.execute(
            """
            SELECT period, COUNT(*) AS rows,
                   COUNT(DISTINCT symbol) AS symbols,
                   MAX(bar_time) AS latest_bar
            FROM kline_intraday
            GROUP BY period
            ORDER BY period
            """
        )
        intraday = [_row_dict(r) for r in cur.fetchall()]

    return {
        **base,
        "stale_days": stale_days,
        "stale_symbols": stale_count,
        "coverage_pct": coverage_pct,
        "intraday": intraday,
    }


def get_issue_breakdown(*, stale_days: int = 5) -> list[dict[str, Any]]:
    summary = get_summary(stale_days=stale_days)
    items = [
        {
            "type": "invalid_close",
            "label": "无效收盘价",
            "severity": "high",
            "count": summary["invalid_close_rows"],
            "description": "close 为空、≤0 或 NaN（PG numeric NaN 会通过 >0 比较）",
        },
        {
            "type": "ohlc_violation",
            "label": "OHLC 逻辑异常",
            "severity": "high",
            "count": summary["ohlc_violation_rows"],
            "description": "high < low，或 open/close 不在 [low, high] 区间",
        },
        {
            "type": "zero_volume",
            "label": "零成交量",
            "severity": "medium",
            "count": summary["zero_volume_rows"],
            "description": "volume = 0 的 K 线（可能是停牌或数据缺失）",
        },
        {
            "type": "stale",
            "label": "行情滞后",
            "severity": "medium",
            "count": summary["stale_symbols"],
            "description": f"上市标的最新日 K 早于全局最新 {stale_days} 天以上",
        },
        {
            "type": "no_kline",
            "label": "无日 K 数据",
            "severity": "high",
            "count": summary["listed_no_kline"],
            "description": "is_listed=true 但在 kline_daily 中无任何记录",
        },
        {
            "type": "orphan",
            "label": "孤儿 K 线",
            "severity": "low",
            "count": summary["orphan_symbols"],
            "description": "kline_daily 中有记录但 symbols 表不存在对应标的",
        },
        {
            "type": "missing_meta",
            "label": "元数据缺失",
            "severity": "low",
            "count": summary["missing_metadata"],
            "description": "上市标的缺少 name 或 sector",
        },
        {
            "type": "sync_failed",
            "label": "同步任务失败",
            "severity": "high",
            "count": summary["failed_jobs_7d"],
            "description": "近 7 天 status=failed 的 sync_jobs",
        },
        {
            "type": "sync_error",
            "label": "同步错误日志",
            "severity": "medium",
            "count": summary["error_logs_7d"],
            "description": "近 7 天 level=error 的 sync_logs",
        },
    ]
    return sorted(items, key=lambda x: (-x["count"], x["type"]))


def list_issues(
    *,
    issue_type: str = "stale",
    page: int = 1,
    page_size: int = 50,
    stale_days: int = 5,
) -> dict[str, Any]:
    page = max(1, page)
    page_size = max(1, min(page_size, 200))
    offset = (page - 1) * page_size
    stale_days = max(1, min(stale_days, 60))

    with get_cursor() as cur:
        if issue_type == "invalid_close":
            cur.execute(
                f"""
                SELECT COUNT(*) AS total FROM kline_daily WHERE {_INVALID_CLOSE}
                """
            )
            total = int(cur.fetchone()["total"])
            cur.execute(
                f"""
                SELECT symbol, trade_date::text AS trade_date, open, high, low, close, volume
                FROM kline_daily
                WHERE {_INVALID_CLOSE}
                ORDER BY trade_date DESC, symbol
                LIMIT %s OFFSET %s
                """,
                (page_size, offset),
            )
            rows = [_row_dict(r) for r in cur.fetchall()]

        elif issue_type == "ohlc_violation":
            cur.execute(
                f"SELECT COUNT(*) AS total FROM kline_daily WHERE {_OHLC_VIOLATION}"
            )
            total = int(cur.fetchone()["total"])
            cur.execute(
                f"""
                SELECT symbol, trade_date::text AS trade_date, open, high, low, close, volume
                FROM kline_daily
                WHERE {_OHLC_VIOLATION}
                ORDER BY trade_date DESC, symbol
                LIMIT %s OFFSET %s
                """,
                (page_size, offset),
            )
            rows = [_row_dict(r) for r in cur.fetchall()]

        elif issue_type == "zero_volume":
            cur.execute("SELECT COUNT(*) AS total FROM kline_daily WHERE volume = 0")
            total = int(cur.fetchone()["total"])
            cur.execute(
                """
                SELECT symbol, trade_date::text AS trade_date, open, high, low, close, volume
                FROM kline_daily
                WHERE volume = 0
                ORDER BY trade_date DESC, symbol
                LIMIT %s OFFSET %s
                """,
                (page_size, offset),
            )
            rows = [_row_dict(r) for r in cur.fetchall()]

        elif issue_type == "stale":
            cur.execute("SELECT MAX(trade_date) AS max_date FROM kline_daily")
            latest = cur.fetchone()["max_date"]
            if not latest:
                return {"items": [], "total": 0, "page": page, "page_size": page_size}
            cur.execute(
                """
                WITH per_symbol AS (
                    SELECT s.symbol, s.name,
                           MAX(k.trade_date) AS last_date,
                           COUNT(k.trade_date) AS bar_count
                    FROM symbols s
                    LEFT JOIN kline_daily k ON k.symbol = s.symbol
                    WHERE s.is_listed = TRUE
                    GROUP BY s.symbol, s.name
                ),
                latest AS (SELECT %s::date AS max_date)
                SELECT symbol, name, last_date::text AS last_date, bar_count,
                       (SELECT max_date FROM latest) - last_date AS days_stale
                FROM per_symbol, latest
                WHERE last_date IS NULL
                   OR last_date < (SELECT max_date FROM latest) - %s * INTERVAL '1 day'
                ORDER BY days_stale DESC NULLS FIRST, symbol
                LIMIT %s OFFSET %s
                """,
                (latest, stale_days, page_size, offset),
            )
            rows = [_row_dict(r) for r in cur.fetchall()]
            cur.execute(
                """
                WITH per_symbol AS (
                    SELECT s.symbol, MAX(k.trade_date) AS last_date
                    FROM symbols s
                    LEFT JOIN kline_daily k ON k.symbol = s.symbol
                    WHERE s.is_listed = TRUE
                    GROUP BY s.symbol
                ),
                latest AS (SELECT %s::date AS max_date)
                SELECT COUNT(*) AS total
                FROM per_symbol, latest
                WHERE last_date IS NULL
                   OR last_date < (SELECT max_date FROM latest) - %s * INTERVAL '1 day'
                """,
                (latest, stale_days),
            )
            total = int(cur.fetchone()["total"])

        elif issue_type == "no_kline":
            cur.execute(
                """
                SELECT COUNT(*) AS total FROM symbols s
                WHERE s.is_listed = TRUE
                  AND NOT EXISTS (
                      SELECT 1 FROM kline_daily k WHERE k.symbol = s.symbol
                  )
                """
            )
            total = int(cur.fetchone()["total"])
            cur.execute(
                """
                SELECT s.symbol, s.name, s.market, s.sector, s.list_date::text AS list_date
                FROM symbols s
                WHERE s.is_listed = TRUE
                  AND NOT EXISTS (
                      SELECT 1 FROM kline_daily k WHERE k.symbol = s.symbol
                  )
                ORDER BY s.symbol
                LIMIT %s OFFSET %s
                """,
                (page_size, offset),
            )
            rows = [_row_dict(r) for r in cur.fetchall()]

        elif issue_type == "orphan":
            cur.execute(
                """
                SELECT COUNT(DISTINCT k.symbol) AS total
                FROM kline_daily k
                WHERE NOT EXISTS (
                    SELECT 1 FROM symbols s WHERE s.symbol = k.symbol
                )
                """
            )
            total = int(cur.fetchone()["total"])
            cur.execute(
                """
                SELECT k.symbol,
                       COUNT(*) AS bar_count,
                       MIN(k.trade_date)::text AS first_date,
                       MAX(k.trade_date)::text AS last_date
                FROM kline_daily k
                WHERE NOT EXISTS (
                    SELECT 1 FROM symbols s WHERE s.symbol = k.symbol
                )
                GROUP BY k.symbol
                ORDER BY bar_count DESC, k.symbol
                LIMIT %s OFFSET %s
                """,
                (page_size, offset),
            )
            rows = [_row_dict(r) for r in cur.fetchall()]

        elif issue_type == "missing_meta":
            cur.execute(
                """
                SELECT COUNT(*) AS total FROM symbols
                WHERE is_listed = TRUE
                  AND (name IS NULL OR name = ''
                       OR sector IS NULL OR sector = '')
                """
            )
            total = int(cur.fetchone()["total"])
            cur.execute(
                """
                SELECT symbol, name, market, sector, industry
                FROM symbols
                WHERE is_listed = TRUE
                  AND (name IS NULL OR name = ''
                       OR sector IS NULL OR sector = '')
                ORDER BY symbol
                LIMIT %s OFFSET %s
                """,
                (page_size, offset),
            )
            rows = [_row_dict(r) for r in cur.fetchall()]

        elif issue_type == "sync_failed":
            cur.execute(
                """
                SELECT COUNT(*) AS total FROM sync_jobs
                WHERE status = 'failed'
                  AND created_at > NOW() - INTERVAL '7 days'
                """
            )
            total = int(cur.fetchone()["total"])
            cur.execute(
                """
                SELECT id, job_type, period, status, progress,
                       symbols_done, symbols_total, message,
                       started_at, finished_at, created_at
                FROM sync_jobs
                WHERE status = 'failed'
                  AND created_at > NOW() - INTERVAL '7 days'
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
                """,
                (page_size, offset),
            )
            rows = [_row_dict(r) for r in cur.fetchall()]

        elif issue_type == "sync_error":
            cur.execute(
                """
                SELECT COUNT(*) AS total FROM sync_logs
                WHERE level = 'error'
                  AND created_at > NOW() - INTERVAL '7 days'
                """
            )
            total = int(cur.fetchone()["total"])
            cur.execute(
                """
                SELECT l.id, l.job_id, l.level, l.symbol, l.message, l.created_at,
                       j.period, j.job_type
                FROM sync_logs l
                LEFT JOIN sync_jobs j ON j.id = l.job_id
                WHERE l.level = 'error'
                  AND l.created_at > NOW() - INTERVAL '7 days'
                ORDER BY l.created_at DESC
                LIMIT %s OFFSET %s
                """,
                (page_size, offset),
            )
            rows = [_row_dict(r) for r in cur.fetchall()]

        else:
            return {
                "items": [],
                "total": 0,
                "page": page,
                "page_size": page_size,
                "error": f"unknown issue_type: {issue_type}",
            }

    return {
        "items": rows,
        "total": total,
        "page": page,
        "page_size": page_size,
        "issue_type": issue_type,
    }
