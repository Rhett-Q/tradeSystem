from __future__ import annotations

import hashlib
import json
import math
import time
from typing import Any

from db.connection import get_cursor
from services.qlib.catalog import get_factor_expression
from services.qlib.factor_conditions import parse_factor_conditions, passes_threshold
from services.qlib.expression import evaluate_expression, required_lookback
from services.qlib.factor_meta import get_factor_info
from services.qlib.panel import get_panel, iter_symbol_frames
from services.screener_filters import EXCLUDE_DELISTED_LABEL, listed_symbol_where
from services.screener_log import ScreenLogger

_QLIB_HIT_CACHE: dict[str, tuple[float, list[dict[str, Any]]]] = {}
_QLIB_CACHE_TTL = 300.0
_QLIB_CACHE_MAX = 8


def _factor_sort_value(row: dict[str, Any], factor: str) -> float | None:
    val = row.get("factor_values", {}).get(factor)
    if val is None:
        return None
    try:
        num = float(val)
    except (TypeError, ValueError):
        return None
    if math.isnan(num) or math.isinf(num):
        return None
    return num


def _parse_sort_rules(
    sort: list[dict[str, Any]] | None,
    sort_by: str,
    factor_names: list[str],
) -> list[dict[str, str]]:
    rules: list[dict[str, str]] = []
    if sort:
        for item in sort:
            factor = str(item.get("factor", "")).strip()
            order = str(item.get("order", "desc")).strip().lower()
            if factor not in factor_names:
                continue
            if order not in ("asc", "desc"):
                order = "desc"
            rules.append({"factor": factor, "order": order})
    elif sort_by.strip() and sort_by.strip() in factor_names:
        rules.append({"factor": sort_by.strip(), "order": "desc"})
    if not rules:
        rules.append({"factor": factor_names[0], "order": "desc"})
    seen: set[str] = set()
    deduped: list[dict[str, str]] = []
    for rule in rules:
        if rule["factor"] in seen:
            continue
        seen.add(rule["factor"])
        deduped.append(rule)
    return deduped[:5]


def _sort_hits(hits: list[dict[str, Any]], sort_rules: list[dict[str, str]]) -> None:
    """多字段排序：规则列表前者优先，支持升序/降序。"""
    for rule in reversed(sort_rules):
        desc = rule["order"] == "desc"
        factor = rule["factor"]

        def key(row: dict[str, Any], *, _f: str = factor, _d: bool = desc) -> float:
            val = _factor_sort_value(row, _f)
            if val is None:
                return float("-inf") if _d else float("inf")
            return val

        hits.sort(key=key, reverse=desc)


def _format_sort_rules(sort_rules: list[dict[str, str]]) -> str:
    parts = []
    for rule in sort_rules:
        arrow = "↓" if rule["order"] == "desc" else "↑"
        parts.append(f"{rule['factor']}{arrow}")
    return ", ".join(parts)


def _qlib_cache_key(
    *,
    factor: str = "",
    conditions: list[dict[str, Any]] | None = None,
    min_value: float | None = None,
    max_value: float | None = None,
    market: str = "",
    sector: str = "",
    library: str = "",
) -> str:
    payload: dict[str, Any] = {
        "market": market,
        "sector": sector,
        "library": library,
    }
    if conditions is not None:
        payload["conditions"] = conditions
    else:
        payload.update({
            "factor": factor,
            "min_value": min_value,
            "max_value": max_value,
        })
    raw = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _get_cached_hits(key: str) -> list[dict[str, Any]] | None:
    item = _QLIB_HIT_CACHE.get(key)
    if not item:
        return None
    ts, hits = item
    if time.time() - ts > _QLIB_CACHE_TTL:
        _QLIB_HIT_CACHE.pop(key, None)
        return None
    return hits


def _set_cached_hits(key: str, hits: list[dict[str, Any]]) -> None:
    if len(_QLIB_HIT_CACHE) >= _QLIB_CACHE_MAX:
        oldest = min(_QLIB_HIT_CACHE, key=lambda k: _QLIB_HIT_CACHE[k][0])
        _QLIB_HIT_CACHE.pop(oldest, None)
    _QLIB_HIT_CACHE[key] = (time.time(), hits)


def _safe_float(value: Any) -> float | None:
    if value is None or (isinstance(value, float) and (math.isnan(value) or math.isinf(value))):
        return None
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(num) or math.isinf(num):
        return None
    return num


def _load_symbol_meta(
    market: str,
    sector: str,
) -> dict[str, dict[str, Any]]:
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


def _parse_conditions(raw: list[dict[str, Any]], library: str = "") -> list[dict[str, Any]]:
    return parse_factor_conditions(raw, library=library)


def _passes_threshold(val: float | None, min_value: float | None, max_value: float | None) -> bool:
    return passes_threshold(val, min_value, max_value)


def _evaluate_symbol_factors(
    frame: Any,
    conditions: list[dict[str, Any]],
) -> dict[str, float] | None:
    values: dict[str, float] = {}
    for cond in conditions:
        try:
            series = evaluate_expression(cond["expression"], frame)
        except ValueError:
            return None
        if series.empty:
            return None
        val = _safe_float(series.iloc[-1])
        if not _passes_threshold(val, cond["min_value"], cond["max_value"]):
            return None
        values[cond["factor"]] = round(val, 6)  # type: ignore[arg-type]
    return values


def _compute_multi_hits(
    panel: Any,
    meta: dict[str, dict[str, Any]],
    conditions: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    hits: list[dict[str, Any]] = []
    stats = {
        "evaluated": 0,
        "skipped_no_data": 0,
        "skipped_eval_error": 0,
        "skipped_threshold": 0,
    }

    for symbol, frame in iter_symbol_frames(panel):
        if symbol not in meta:
            continue
        stats["evaluated"] += 1
        values = _evaluate_symbol_factors(frame, conditions)
        if values is None:
            # Distinguish eval error vs threshold - simplified: count as threshold
            stats["skipped_threshold"] += 1
            continue

        last = frame.iloc[-1]
        trade_date = frame.index[-1]
        hits.append({
            "symbol": symbol,
            "name": meta[symbol].get("name") or "",
            "market": meta[symbol].get("market") or "",
            "sector": meta[symbol].get("sector"),
            "trade_date": trade_date.strftime("%Y-%m-%d")
            if hasattr(trade_date, "strftime")
            else str(trade_date)[:10],
            "close": _safe_float(last.get("close")),
            "volume": int(last.get("volume") or 0),
            "factor_values": values,
        })

    return hits, stats


def run_multi_qlib_screen(
    *,
    conditions: list[dict[str, Any]],
    market: str = "",
    sector: str = "",
    page: int = 1,
    page_size: int = 50,
    sort: list[dict[str, Any]] | None = None,
    sort_by: str = "",
    library: str = "",
) -> dict[str, Any]:
    log = ScreenLogger("multi")
    parsed = _parse_conditions(conditions, library=library)
    factor_names = [c["factor"] for c in parsed]
    sort_rules = _parse_sort_rules(sort, sort_by, factor_names)

    log.info(f"开始多因子筛选 · {' AND '.join(factor_names)}")
    log.info(f"排序 · {_format_sort_rules(sort_rules)}")
    log.info(f"条件 · {EXCLUDE_DELISTED_LABEL}")
    for cond in parsed:
        parts = [cond["factor"]]
        if cond["min_value"] is not None:
            parts.append(f"≥ {cond['min_value']}")
        if cond["max_value"] is not None:
            parts.append(f"≤ {cond['max_value']}")
        log.info(f"条件 · {' '.join(parts)}")

    lookback = max(max(required_lookback(c["expression"]) for c in parsed), 90)
    cache_key = _qlib_cache_key(conditions=[
        {
            "factor": c["factor"],
            "min_value": c["min_value"],
            "max_value": c["max_value"],
        }
        for c in parsed
    ], market=market, sector=sector, library=library)
    cached_hits = _get_cached_hits(cache_key)

    if cached_hits is not None:
        log.info(f"使用缓存命中列表 · {len(cached_hits)} 只 · 第 {page} 页")
        log.set_stat("cache_hit", True)
        hits = cached_hits
    else:
        log.info(f"估算回溯窗口 · {lookback} 日历日")
        log.set_stat("cache_hit", False)
        log.set_stat("lookback_days", lookback)

        t0 = time.perf_counter()
        panel = get_panel(lookback)
        panel_ms = round((time.perf_counter() - t0) * 1000, 1)
        log.set_stat("panel_load_ms", panel_ms)

        if panel.empty:
            log.warn("无日 K 数据，请先同步日线")
            log.finish("筛选结束")
            return log.attach({
                "total": 0,
                "page": page,
                "page_size": page_size,
                "factors": factor_names,
                "conditions": parsed,
                "sort": sort_rules,
                "rows": [],
                "message": "无日 K 数据，请先同步日线",
            })

        symbols_in_panel = panel.index.get_level_values(0).nunique()
        log.info(f"加载面板 · {len(panel):,} 行 · {symbols_in_panel} 只 · 耗时 {panel_ms}ms")

        meta = _load_symbol_meta(market, sector)
        log.info(f"标的池（元数据过滤后）· {len(meta)} 只")
        log.set_stat("universe", len(meta))

        if not meta:
            log.warn("标的池为空，请检查市场/板块条件")
            log.finish("筛选结束")
            return log.attach({
                "total": 0,
                "page": page,
                "page_size": page_size,
                "factors": factor_names,
                "conditions": parsed,
                "sort": sort_rules,
                "rows": [],
            })

        t1 = time.perf_counter()
        hits, eval_stats = _compute_multi_hits(panel, meta, parsed)
        compute_ms = round((time.perf_counter() - t1) * 1000, 1)
        for key, val in eval_stats.items():
            log.set_stat(key, val)
        log.set_stat("compute_ms", compute_ms)

        log.info(
            f"多因子计算完成 · 评估 {eval_stats['evaluated']} 只 · 命中 {len(hits)} 只 · "
            f"耗时 {compute_ms}ms",
        )

        _set_cached_hits(cache_key, hits)

    hits = list(hits)
    _sort_hits(hits, sort_rules)

    total = len(hits)
    offset = (page - 1) * page_size
    page_rows = hits[offset : offset + page_size]
    log.set_stat("matched", total)
    log.set_stat("factor_count", len(parsed))

    if total == 0:
        log.warn("无命中结果，可放宽阈值或减少因子条件")
    else:
        from_idx = offset + 1
        to_idx = min(offset + page_size, total)
        log.info(f"返回第 {page} 页 · 第 {from_idx}–{to_idx} 条 / 共 {total} 条")

    log.finish(f"多因子筛选完成，总耗时 {log.stats.get('total_ms', 0)}ms")

    return log.attach({
        "total": total,
        "page": page,
        "page_size": page_size,
        "factors": factor_names,
        "conditions": parsed,
        "sort": sort_rules,
        "lookback_days": lookback,
        "rows": page_rows,
    })


def run_qlib_screen(
    *,
    factor: str,
    min_value: float | None = None,
    max_value: float | None = None,
    market: str = "",
    sector: str = "",
    page: int = 1,
    page_size: int = 50,
    library: str = "",
) -> dict[str, Any]:
    log = ScreenLogger("qlib")
    log.info(f"开始 Qlib 因子筛选 · {factor}")

    expr = get_factor_expression(factor, library)
    if not expr:
        raise ValueError(f"未知因子: {factor}")

    log.info(f"条件 · {EXCLUDE_DELISTED_LABEL}")
    factor_info = get_factor_info(factor, expr)
    log.info(f"表达式 · {expr}")
    log.info(f"含义 · {factor_info['description']}")

    if min_value is not None:
        log.info(f"条件 · 因子值 ≥ {min_value}")
    if max_value is not None:
        log.info(f"条件 · 因子值 ≤ {max_value}")
    if market:
        log.info(f"条件 · 市场 = {market}")
    if sector:
        log.info(f"条件 · 板块 = {sector}")

    lookback = max(required_lookback(expr), 90)
    cache_key = _qlib_cache_key(
        factor=factor,
        min_value=min_value,
        max_value=max_value,
        market=market,
        sector=sector,
        library=library,
    )
    cached_hits = _get_cached_hits(cache_key)

    if cached_hits is not None:
        log.info(f"使用缓存命中列表 · {len(cached_hits)} 只 · 第 {page} 页")
        log.set_stat("cache_hit", True)
        hits = cached_hits
        evaluated = log.stats.get("evaluated", len(hits))
        skipped_no_data = 0
        skipped_eval_error = 0
        skipped_threshold = 0
        compute_ms = 0
        panel_ms = 0
        lookback = log.stats.get("lookback_days", lookback)
    else:
        log.info(f"估算回溯窗口 · {lookback} 日历日")

        t0 = time.perf_counter()
        panel = get_panel(lookback)
        panel_ms = round((time.perf_counter() - t0) * 1000, 1)
        log.set_stat("lookback_days", lookback)
        log.set_stat("panel_load_ms", panel_ms)
        log.set_stat("cache_hit", False)

        if panel.empty:
            log.warn("无日 K 数据，请先同步日线")
            log.finish("筛选结束")
            return log.attach({
                "total": 0,
                "page": page,
                "page_size": page_size,
                "factor": factor,
                "expression": expr,
                "factor_info": factor_info,
                "rows": [],
                "message": "无日 K 数据，请先同步日线",
            })

        symbols_in_panel = panel.index.get_level_values(0).nunique()
        log.info(f"加载面板 · {len(panel):,} 行 · {symbols_in_panel} 只 · 耗时 {panel_ms}ms")

        meta = _load_symbol_meta(market, sector)
        log.info(f"标的池（元数据过滤后）· {len(meta)} 只")
        log.set_stat("universe", len(meta))

        if not meta:
            log.warn("标的池为空，请检查市场/板块条件")
            log.finish("筛选结束")
            return log.attach({
                "total": 0,
                "page": page,
                "page_size": page_size,
                "factor": factor,
                "expression": expr,
                "factor_info": factor_info,
                "rows": [],
            })

        hits = []
        evaluated = 0
        skipped_no_data = 0
        skipped_eval_error = 0
        skipped_threshold = 0

        t1 = time.perf_counter()
        for symbol, frame in iter_symbol_frames(panel):
            if symbol not in meta:
                continue
            evaluated += 1
            try:
                series = evaluate_expression(expr, frame)
            except ValueError:
                skipped_eval_error += 1
                continue
            if series.empty:
                skipped_no_data += 1
                continue
            val = _safe_float(series.iloc[-1])
            if val is None:
                skipped_no_data += 1
                continue
            if min_value is not None and val < min_value:
                skipped_threshold += 1
                continue
            if max_value is not None and val > max_value:
                skipped_threshold += 1
                continue

            last = frame.iloc[-1]
            trade_date = frame.index[-1]
            hits.append(
                {
                    "symbol": symbol,
                    "name": meta[symbol].get("name") or "",
                    "market": meta[symbol].get("market") or "",
                    "sector": meta[symbol].get("sector"),
                    "trade_date": trade_date.strftime("%Y-%m-%d")
                    if hasattr(trade_date, "strftime")
                    else str(trade_date)[:10],
                    "close": _safe_float(last.get("close")),
                    "volume": int(last.get("volume") or 0),
                    "factor": factor,
                    "factor_value": round(val, 6),
                },
            )

        compute_ms = round((time.perf_counter() - t1) * 1000, 1)
        log.set_stat("evaluated", evaluated)
        log.set_stat("skipped_no_data", skipped_no_data)
        log.set_stat("skipped_eval_error", skipped_eval_error)
        log.set_stat("skipped_threshold", skipped_threshold)
        log.set_stat("compute_ms", compute_ms)

        log.info(
            f"因子计算完成 · 评估 {evaluated} 只 · 命中 {len(hits)} 只 · "
            f"无数据 {skipped_no_data} · 表达式失败 {skipped_eval_error} · "
            f"阈值过滤 {skipped_threshold} · 耗时 {compute_ms}ms",
        )

        hits.sort(key=lambda r: r["factor_value"], reverse=True)
        _set_cached_hits(cache_key, hits)

    total = len(hits)
    offset = (page - 1) * page_size
    page_rows = hits[offset : offset + page_size]
    log.set_stat("matched", total)

    if total == 0:
        log.warn("无命中结果，可放宽 min_value/max_value 或更换因子")
    else:
        from_idx = offset + 1
        to_idx = min(offset + page_size, total)
        log.info(f"返回第 {page} 页 · 第 {from_idx}–{to_idx} 条 / 共 {total} 条")

    log.finish(f"Qlib 因子筛选完成，总耗时 {log.stats.get('total_ms', 0)}ms")

    return log.attach({
        "total": total,
        "page": page,
        "page_size": page_size,
        "factor": factor,
        "expression": expr,
        "factor_info": factor_info,
        "lookback_days": lookback,
        "rows": page_rows,
    })


__all__ = ["run_qlib_screen", "run_multi_qlib_screen"]
