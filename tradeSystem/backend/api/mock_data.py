"""Mock 数据 — 仅用于 UI 原型，不含真实业务逻辑。"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

NOW = datetime(2026, 6, 10, 15, 0, 0)


def health() -> dict[str, Any]:
    return {
        "minqmt_connected": True,
        "minqmt_account": "模拟账户",
        "postgres_connected": True,
        "postgres_host": "127.0.0.1:5432/trade_db",
        "last_sync_at": (NOW - timedelta(hours=2)).isoformat(),
        "universe_count": 5124,
        "kline_rows": 18_420_000,
    }


def sync_jobs() -> list[dict[str, Any]]:
    return [
        {
            "id": "job-001",
            "type": "incremental",
            "period": "1d",
            "status": "completed",
            "progress": 100,
            "symbols_total": 5124,
            "symbols_done": 5124,
            "started_at": (NOW - timedelta(hours=2, minutes=18)).isoformat(),
            "finished_at": (NOW - timedelta(hours=1, minutes=52)).isoformat(),
            "message": "增量同步完成",
        },
        {
            "id": "job-002",
            "type": "full",
            "period": "1d",
            "status": "running",
            "progress": 67,
            "symbols_total": 5124,
            "symbols_done": 3433,
            "started_at": (NOW - timedelta(minutes=25)).isoformat(),
            "finished_at": None,
            "message": "正在下载 K 线…",
        },
        {
            "id": "job-003",
            "type": "incremental",
            "period": "5m",
            "status": "failed",
            "progress": 12,
            "symbols_total": 800,
            "symbols_done": 96,
            "started_at": (NOW - timedelta(days=1)).isoformat(),
            "finished_at": (NOW - timedelta(days=1, hours=-1)).isoformat(),
            "message": "MiniQMT 连接超时",
        },
    ]


def symbols(page: int = 1, page_size: int = 20) -> dict[str, Any]:
    base = [
        {"symbol": "600519.SH", "name": "贵州茅台", "market": "SH", "sector": "白酒", "listed": True},
        {"symbol": "000858.SZ", "name": "五粮液", "market": "SZ", "sector": "白酒", "listed": True},
        {"symbol": "601318.SH", "name": "中国平安", "market": "SH", "sector": "保险", "listed": True},
        {"symbol": "300750.SZ", "name": "宁德时代", "market": "SZ", "sector": "新能源", "listed": True},
        {"symbol": "600036.SH", "name": "招商银行", "market": "SH", "sector": "银行", "listed": True},
    ]
    rows = base * 4
    start = (page - 1) * page_size
    return {
        "total": 5124,
        "page": page,
        "page_size": page_size,
        "rows": rows[start : start + page_size],
    }


def kline_preview(symbol: str = "600519.SH") -> dict[str, Any]:
    rows = []
    price = 1680.0
    for i in range(30):
        d = NOW - timedelta(days=29 - i)
        o = price
        c = price + (i % 5 - 2) * 3.5
        rows.append(
            {
                "date": d.strftime("%Y-%m-%d"),
                "open": round(o, 2),
                "high": round(max(o, c) + 5, 2),
                "low": round(min(o, c) - 4, 2),
                "close": round(c, 2),
                "volume": 1_200_000 + i * 10_000,
                "amount": 2.1e9 + i * 1e7,
            }
        )
        price = c
    return {"symbol": symbol, "period": "1d", "rows": rows}


def db_tables() -> list[dict[str, Any]]:
    return [
        {"name": "symbols", "rows": 5124, "size_mb": 1.2, "last_updated": NOW.isoformat()},
        {"name": "kline_daily", "rows": 12_800_000, "size_mb": 890.5, "last_updated": NOW.isoformat()},
        {"name": "kline_5m", "rows": 5_620_000, "size_mb": 1240.0, "last_updated": (NOW - timedelta(days=1)).isoformat()},
        {"name": "sync_jobs", "rows": 128, "size_mb": 0.3, "last_updated": NOW.isoformat()},
        {"name": "sync_logs", "rows": 4520, "size_mb": 2.1, "last_updated": NOW.isoformat()},
    ]


def settings() -> dict[str, Any]:
    return {
        "minqmt": {
            "path": r"D:\gjqmt",
            "account": "",
            "auto_connect": True,
        },
        "postgres": {
            "host": "127.0.0.1",
            "port": 5432,
            "database": "trade_db",
            "user": "trade_user",
        },
        "sync": {
            "default_period": "1d",
            "batch_size": 200,
            "start_date": "20200101",
            "schedule_cron": "0 18 * * 1-5",
        },
    }
