from __future__ import annotations

import math
from typing import Any

import backtrader as bt
import pandas as pd

from services.qlib.expression import evaluate_expression, required_lookback
from services.qlib.factor_conditions import parse_factor_conditions, passes_threshold


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


def compute_signal_series(
    frame: pd.DataFrame,
    conditions: list[dict[str, Any]],
) -> pd.Series:
    """按日计算多因子 AND 信号（1=全部满足，0=否则）。"""
    frame = frame.sort_index()
    mask = pd.Series(True, index=frame.index)
    for cond in conditions:
        series = evaluate_expression(cond["expression"], frame)
        cond_mask = series.notna()
        if cond["min_value"] is not None:
            cond_mask &= series >= cond["min_value"]
        if cond["max_value"] is not None:
            cond_mask &= series <= cond["max_value"]
        mask &= cond_mask
    return mask.astype(float)


def required_lookback_for_conditions(conditions: list[dict[str, Any]]) -> int:
    if not conditions:
        return 65
    return max(max(required_lookback(c["expression"]) for c in conditions), 90)


def make_signal_feed(df: pd.DataFrame) -> bt.feeds.PandasData:
    return bt.feeds.PandasData(
        dataname=df,
        datetime=None,
        open="open",
        high="high",
        low="low",
        close="close",
        volume="volume",
        openinterest=-1,
        signal="signal",
    )


class SignalPandasData(bt.feeds.PandasData):
    lines = ("signal",)
    params = (
        ("datetime", None),
        ("open", "open"),
        ("high", "high"),
        ("low", "low"),
        ("close", "close"),
        ("volume", "volume"),
        ("openinterest", -1),
        ("signal", "signal"),
    )


def make_signal_feed_v2(df: pd.DataFrame) -> SignalPandasData:
    return SignalPandasData(dataname=df)


def public_conditions(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    parsed = parse_factor_conditions(raw)
    return [
        {
            "factor": c["factor"],
            "min_value": c["min_value"],
            "max_value": c["max_value"],
        }
        for c in parsed
    ]
