from __future__ import annotations

import time
from typing import Any

import numpy as np
import pandas as pd

from services.qlib.catalog import get_factor_expression, list_factor_names, normalize_library
from services.qlib.expression import evaluate_expression, required_lookback
from services.qlib.panel import get_panel, iter_symbol_frames
from services.qlib.screener_service import _load_symbol_meta
from services.qlib.train_log import TrainLogger


def _forward_label(close: pd.Series, days: int) -> pd.Series:
    return close.shift(-days) / close - 1.0


def _compute_panel_lookback(
    expressions: dict[str, str],
    start: pd.Timestamp,
    label_days: int,
) -> int:
    expr_lb = max(required_lookback(expr) for expr in expressions.values())
    span_days = (pd.Timestamp.now().normalize() - start).days + label_days + 30
    return max(expr_lb + label_days + 15, span_days, 90)


def build_training_dataset(
    *,
    library: str = "alpha158",
    factors: list[str] | None = None,
    start_date: str,
    end_date: str,
    label_days: int = 5,
    market: str = "",
    sector: str = "",
    max_symbols: int = 800,
    log: TrainLogger | None = None,
) -> tuple[pd.DataFrame, pd.Series, dict[str, Any]]:
    """构建 (features, label) 训练集。"""
    lib = normalize_library(library)
    factor_names = factors or list_factor_names(lib)
    if not factor_names:
        raise ValueError("因子列表为空")

    if log:
        log.info(f"因子库 · {lib} · {len(factor_names)} 个特征")
        log.info(f"日期范围 · {start_date} ~ {end_date} · 标签 {label_days} 日收益")
        if market:
            log.info(f"市场过滤 · {market}")
        if sector:
            log.info(f"板块过滤 · {sector}")
        log.info(f"最大标的数 · {max_symbols}")

    expressions: dict[str, str] = {}
    for name in factor_names:
        expr = get_factor_expression(name, lib)
        if not expr:
            raise ValueError(f"未知因子: {name}")
        expressions[name] = expr

    start = pd.Timestamp(start_date).normalize()
    end = pd.Timestamp(end_date).normalize()
    if start >= end:
        raise ValueError("start_date 必须早于 end_date")

    lookback = _compute_panel_lookback(expressions, start, label_days)
    if log:
        log.info(f"面板回溯窗口 · {lookback} 日历日（含 start_date 覆盖）")

    t0 = time.perf_counter()
    panel = get_panel(lookback)
    panel_ms = round((time.perf_counter() - t0) * 1000, 1)

    if panel.empty:
        raise ValueError("无日 K 数据，请先同步日线")

    panel_symbols = panel.index.get_level_values(0).nunique()
    panel_dates = panel.index.get_level_values(1)
    if log:
        log.info(
            f"加载面板 · {len(panel):,} 行 · {panel_symbols} 只 · "
            f"{panel_dates.min().date()} ~ {panel_dates.max().date()} · 耗时 {panel_ms}ms",
        )

    meta = _load_symbol_meta(market, sector)
    symbols = [sym for sym, _ in iter_symbol_frames(panel) if sym in meta]
    if max_symbols and len(symbols) > max_symbols:
        symbols = symbols[:max_symbols]
        if log:
            log.info(f"标的截断 · 取前 {max_symbols} 只 / 池内 {len(meta)} 只")

    if log:
        log.info(f"训练标的 · {len(symbols)} 只")

    chunks: list[pd.DataFrame] = []
    skipped_empty = 0
    raw_rows_before_clean = 0
    nan_fill_rows = 0

    t1 = time.perf_counter()
    for idx, symbol in enumerate(symbols):
        frame = panel.xs(symbol, level=0).copy()
        close = frame["close"].astype(float)
        label = _forward_label(close, label_days)
        rows: dict[str, pd.Series] = {}
        eval_errors = 0
        for name, expr in expressions.items():
            try:
                rows[name] = evaluate_expression(expr, frame)
            except ValueError:
                eval_errors += 1
                rows[name] = pd.Series(np.nan, index=frame.index)

        block = pd.DataFrame(rows, index=frame.index)
        block["label"] = label
        block["symbol"] = symbol
        block = block.reset_index(names="trade_date")
        block = block[(block["trade_date"] >= start) & (block["trade_date"] <= end)]
        block = block.dropna(subset=["label"])
        if block.empty:
            skipped_empty += 1
            continue

        raw_rows_before_clean += len(block)
        feat = block[factor_names].replace([np.inf, -np.inf], np.nan)
        nan_mask = feat.isna().any(axis=1)
        nan_fill_rows += int(nan_mask.sum())
        block[factor_names] = feat.fillna(0.0)
        chunks.append(block)

        if log and (idx + 1) % 100 == 0:
            log.info(f"特征计算进度 · {idx + 1}/{len(symbols)} 只 · 累计样本 {raw_rows_before_clean:,}")

    build_ms = round((time.perf_counter() - t1) * 1000, 1)

    if not chunks:
        msg = (
            f"无有效训练样本（标的 {len(symbols)} 只，日期 {start_date}~{end_date}）。"
            f"请扩大日期范围、减小因子数，或检查面板是否覆盖 start_date"
        )
        if log:
            log.warn(msg)
            log.set_stat("skipped_symbols", skipped_empty)
        raise ValueError(msg)

    data = pd.concat(chunks, ignore_index=True)
    y = data["label"].astype(float)
    x = data[factor_names].astype(float)

    label_stats = {
        "mean": round(float(y.mean()), 6),
        "std": round(float(y.std()), 6),
        "min": round(float(y.min()), 6),
        "max": round(float(y.max()), 6),
    }

    meta_info = {
        "library_id": lib,
        "factors": factor_names,
        "factor_count": len(factor_names),
        "start_date": start.strftime("%Y-%m-%d"),
        "end_date": end.strftime("%Y-%m-%d"),
        "label_days": label_days,
        "lookback_days": lookback,
        "samples": len(x),
        "symbols": int(data["symbol"].nunique()),
        "skipped_symbols": skipped_empty,
        "rows_with_nan_filled": nan_fill_rows,
        "label_stats": label_stats,
        "panel_load_ms": panel_ms,
        "feature_build_ms": build_ms,
    }

    if log:
        log.info(
            f"数据集就绪 · {len(x):,} 样本 · {meta_info['symbols']} 只 · "
            f"跳过空标的 {skipped_empty} · NaN 填 0 行 {nan_fill_rows:,} · 耗时 {build_ms}ms",
        )
        log.info(
            f"标签统计 · mean={label_stats['mean']} std={label_stats['std']} "
            f"min={label_stats['min']} max={label_stats['max']}",
        )
        for k, v in meta_info.items():
            if k != "label_stats":
                log.set_stat(k, v)
        log.set_stat("label_stats", label_stats)

    return x, y, meta_info
