from __future__ import annotations

from typing import Any

import pandas as pd

# 由 PG 日 K 重采样得到的周期（不同步、不落库）
RESAMPLE_FROM_DAILY = frozenset({"1w", "1mon"})

_RESAMPLE_RULE = {"1w": "W-FRI", "1mon": "ME"}


def daily_fetch_limit(period: str, limit: int) -> int:
    """估算重采样所需的日线条数。"""
    if period == "1w":
        return max(limit * 8 + 30, 400)
    if period == "1mon":
        return max(limit * 32 + 60, 800)
    return limit


def resample_daily_rows(rows: list[dict[str, Any]], period: str) -> list[dict[str, Any]]:
    """将日 K 行列表重采样为周线/月线。"""
    if not rows or period not in _RESAMPLE_RULE:
        return rows

    df = pd.DataFrame(rows)
    df["trade_date"] = pd.to_datetime(df["date"])
    df = df.set_index("trade_date").sort_index()

    agg = (
        df.resample(_RESAMPLE_RULE[period])
        .agg(
            {
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
                "amount": "sum",
            },
        )
        .dropna(subset=["open"])
    )

    result: list[dict[str, Any]] = []
    for ts, row in agg.iterrows():
        result.append(
            {
                "date": ts.date().isoformat(),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": int(row["volume"] or 0),
                "amount": float(row["amount"] or 0),
            },
        )
    return result
