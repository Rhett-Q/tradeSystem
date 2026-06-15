from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from services.qlib.catalog import get_factor_expression, normalize_library, resolve_factor_library
from services.qlib.expression import evaluate_expression, required_lookback
from services.qlib.panel import get_panel, iter_symbol_frames
from services.qlib.screener_service import _load_symbol_meta, _safe_float


def _parse_date(value: str) -> pd.Timestamp:
    return pd.Timestamp(value).normalize()


def _forward_return(close: pd.Series, days: int) -> pd.Series:
    return close.shift(-days) / close - 1.0


def _sample_dates(dates: pd.DatetimeIndex, max_points: int = 60) -> pd.DatetimeIndex:
    unique = dates.unique().sort_values()
    if len(unique) <= max_points:
        return unique
    step = max(1, len(unique) // max_points)
    return unique[::step]


def compute_factor_ic(
    *,
    factor: str,
    library: str = "alpha158",
    start_date: str,
    end_date: str,
    forward_days: int = 5,
    market: str = "",
    sector: str = "",
    quintiles: int = 5,
    max_dates: int = 60,
) -> dict[str, Any]:
    lib = normalize_library(library)
    resolved = resolve_factor_library(factor, lib)
    if not resolved:
        raise ValueError(f"因子 {factor} 不在库 {lib} 中")

    expr = get_factor_expression(factor, resolved)
    if not expr:
        raise ValueError(f"未知因子: {factor}")

    start = _parse_date(start_date)
    end = _parse_date(end_date)
    if start >= end:
        raise ValueError("start_date 必须早于 end_date")
    if forward_days < 1 or forward_days > 20:
        raise ValueError("forward_days 支持 1–20")

    lookback = max(required_lookback(expr), 70) + forward_days + 10
    panel = get_panel(lookback)
    if panel.empty:
        return {
            "factor": factor,
            "library_id": resolved,
            "expression": expr,
            "message": "无日 K 数据，请先同步日线",
            "ic_mean": None,
            "ic_std": None,
            "ic_ir": None,
            "ic_positive_ratio": None,
            "ic_series": [],
            "quintile_returns": [],
            "stats": {"evaluated_symbols": 0, "sample_dates": 0},
        }

    meta = _load_symbol_meta(market, sector)
    factor_rows: list[dict[str, Any]] = []
    label_rows: list[dict[str, Any]] = []

    for symbol, frame in iter_symbol_frames(panel):
        if symbol not in meta:
            continue
        close = frame["close"].astype(float)
        try:
            factor_series = evaluate_expression(expr, frame)
        except ValueError:
            continue
        label_series = _forward_return(close, forward_days)

        for dt in frame.index:
            if dt < start or dt > end:
                continue
            fv = _safe_float(factor_series.loc[dt] if dt in factor_series.index else np.nan)
            lv = _safe_float(label_series.loc[dt] if dt in label_series.index else np.nan)
            if fv is None or lv is None:
                continue
            factor_rows.append({"date": dt, "symbol": symbol, "value": fv})
            label_rows.append({"date": dt, "symbol": symbol, "label": lv})

    if not factor_rows:
        raise ValueError("样本不足：请扩大日期范围或检查市场/板块过滤")

    fdf = pd.DataFrame(factor_rows)
    ldf = pd.DataFrame(label_rows)
    merged = fdf.merge(ldf, on=["date", "symbol"], how="inner")
    if merged.empty:
        raise ValueError("因子与收益无法对齐")

    eval_dates = _sample_dates(pd.DatetimeIndex(merged["date"].unique()), max_points=max_dates)
    ic_records: list[dict[str, Any]] = []
    quintile_acc: dict[int, list[float]] = {i: [] for i in range(1, quintiles + 1)}

    for dt in eval_dates:
        day = merged[merged["date"] == dt]
        if len(day) < quintiles * 3:
            continue
        x = day["value"].astype(float)
        y = day["label"].astype(float)
        if x.std() == 0 or y.std() == 0:
            continue
        ic = float(x.corr(y, method="spearman"))
        if math.isnan(ic):
            continue
        ic_records.append({
            "date": dt.strftime("%Y-%m-%d"),
            "ic": round(ic, 6),
            "count": len(day),
        })

        try:
            buckets = pd.qcut(x.rank(method="first"), quintiles, labels=False) + 1
        except ValueError:
            continue
        for q in range(1, quintiles + 1):
            mask = buckets == q
            if mask.sum() == 0:
                continue
            quintile_acc[q].append(float(y[mask].mean()))

    if not ic_records:
        raise ValueError("有效 IC 样本不足，请扩大日期范围或减少 forward_days")

    ic_vals = [r["ic"] for r in ic_records]
    ic_mean = float(np.mean(ic_vals))
    ic_std = float(np.std(ic_vals, ddof=1)) if len(ic_vals) > 1 else 0.0
    ic_ir = ic_mean / ic_std if ic_std > 1e-12 else None

    quintile_returns = []
    for q in range(1, quintiles + 1):
        samples = quintile_acc[q]
        quintile_returns.append({
            "group": q,
            "label": f"Q{q}",
            "mean_return": round(float(np.mean(samples)), 6) if samples else None,
            "samples": len(samples),
        })

    long_short = None
    if quintile_returns[0]["mean_return"] is not None and quintile_returns[-1]["mean_return"] is not None:
        long_short = round(
            quintile_returns[-1]["mean_return"] - quintile_returns[0]["mean_return"],
            6,
        )

    return {
        "factor": factor,
        "library_id": resolved,
        "expression": expr,
        "start_date": start.strftime("%Y-%m-%d"),
        "end_date": end.strftime("%Y-%m-%d"),
        "forward_days": forward_days,
        "ic_mean": round(ic_mean, 6),
        "ic_std": round(ic_std, 6),
        "ic_ir": round(ic_ir, 6) if ic_ir is not None else None,
        "ic_positive_ratio": round(sum(1 for v in ic_vals if v > 0) / len(ic_vals), 4),
        "ic_series": ic_records,
        "quintile_returns": quintile_returns,
        "long_short_spread": long_short,
        "stats": {
            "evaluated_symbols": merged["symbol"].nunique(),
            "sample_dates": len(ic_records),
            "total_observations": len(merged),
        },
    }
