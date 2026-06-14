from __future__ import annotations

from datetime import date, datetime
from typing import Any


def parse_trade_date(value: Any) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, (int, float)):
        s = str(int(value))
        if len(s) >= 8:
            return date(int(s[:4]), int(s[4:6]), int(s[6:8]))
        raise ValueError(f"无法解析日期: {value}")
    s = str(value).strip()
    if len(s) >= 8 and s[:8].isdigit():
        s8 = s[:8]
        return date(int(s8[:4]), int(s8[4:6]), int(s8[6:8]))
    return datetime.fromisoformat(s.replace("Z", "+00:00")).date()


def parse_bar_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        iv = int(value)
        if iv > 1_000_000_000_000:
            return datetime.fromtimestamp(iv / 1000)
        s = str(iv)
        if len(s) == 14:
            return datetime.strptime(s, "%Y%m%d%H%M%S")
        if len(s) == 8:
            return datetime.strptime(s, "%Y%m%d")
    s = str(value).strip()
    if len(s) == 14 and s.isdigit():
        return datetime.strptime(s, "%Y%m%d%H%M%S")
    if len(s) == 8 and s.isdigit():
        return datetime.strptime(s, "%Y%m%d")
    return datetime.fromisoformat(s.replace("Z", "+00:00"))
