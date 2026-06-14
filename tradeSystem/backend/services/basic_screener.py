from __future__ import annotations

import time
from typing import Any

from db.repositories import screener as screener_repo
from services.screener_filters import EXCLUDE_DELISTED_LABEL
from services.screener_log import ScreenLogger


def _describe_basic_filters(**kwargs: Any) -> list[str]:
    lines: list[str] = [EXCLUDE_DELISTED_LABEL]
    if kwargs.get("market"):
        lines.append(f"市场 = {kwargs['market']}")
    if kwargs.get("sector"):
        lines.append(f"板块 = {kwargs['sector']}")
    if kwargs.get("min_close") is not None:
        lines.append(f"收盘价 ≥ {kwargs['min_close']}")
    if kwargs.get("max_close") is not None:
        lines.append(f"收盘价 ≤ {kwargs['max_close']}")
    cd = kwargs.get("change_days", 5)
    if kwargs.get("min_change_pct") is not None:
        lines.append(f"{cd} 日涨幅 ≥ {kwargs['min_change_pct']}%")
    if kwargs.get("max_change_pct") is not None:
        lines.append(f"{cd} 日涨幅 ≤ {kwargs['max_change_pct']}%")
    if kwargs.get("min_volume") is not None:
        lines.append(f"成交量 ≥ {kwargs['min_volume']}")
    if kwargs.get("above_ma"):
        lines.append(f"收盘价 ≥ MA{kwargs['above_ma']}")
    if kwargs.get("below_ma"):
        lines.append(f"收盘价 ≤ MA{kwargs['below_ma']}")
    if not lines:
        lines.append("无额外条件（全市场有效日 K 标的）")
    return lines


def run_basic_screen(**kwargs: Any) -> dict[str, Any]:
    log = ScreenLogger("basic")
    log.info("开始基础筛选")
    for line in _describe_basic_filters(**kwargs):
        log.info(f"条件 · {line}")

    t0 = time.perf_counter()
    result = screener_repo.screen(**kwargs)
    query_ms = round((time.perf_counter() - t0) * 1000, 1)

    log.info(f"PostgreSQL 查询完成，耗时 {query_ms}ms")
    log.set_stat("query_ms", query_ms)
    log.set_stat("matched", result.get("total", 0))
    log.set_stat("page", result.get("page", 1))
    log.set_stat("page_size", result.get("page_size", 50))
    log.set_stat("returned", len(result.get("rows", [])))

    total = result.get("total", 0)
    page = result.get("page", 1)
    page_size = result.get("page_size", 50)
    if total == 0:
        log.warn("未命中任何标的，请放宽条件或确认日 K 已同步")
    else:
        from_idx = (page - 1) * page_size + 1
        to_idx = min(page * page_size, total)
        log.info(f"命中 {total} 只，本页第 {from_idx}–{to_idx} 条（共 {len(result.get('rows', []))} 条）")

    log.finish(f"基础筛选完成，总耗时 {log.stats.get('total_ms', 0)}ms")
    return log.attach(result)
