from __future__ import annotations

import re

import numpy as np
import pandas as pd

_DOLLAR_FIELDS = ("close", "open", "high", "low", "volume", "vwap")


def _ref(series: pd.Series, n) -> pd.Series:
    return series.shift(int(n))


def _mean(series: pd.Series, n) -> pd.Series:
    return series.rolling(int(n), min_periods=int(n)).mean()


def _std(series: pd.Series, n) -> pd.Series:
    return series.rolling(int(n), min_periods=int(n)).std()


def _sum(series: pd.Series, n) -> pd.Series:
    return series.rolling(int(n), min_periods=int(n)).sum()


def _max(series: pd.Series, n) -> pd.Series:
    return series.rolling(int(n), min_periods=int(n)).max()


def _min(series: pd.Series, n) -> pd.Series:
    return series.rolling(int(n), min_periods=int(n)).min()


def _abs(series: pd.Series) -> pd.Series:
    return series.abs()


def _log(series: pd.Series) -> pd.Series:
    return np.log(series.astype(float))


def _greater(a, b):
    return np.maximum(a, b)


def _less(a, b):
    return np.minimum(a, b)


def _corr(a: pd.Series, b: pd.Series, n) -> pd.Series:
    n = int(n)
    return a.rolling(n, min_periods=n).corr(b)


def _slope(series: pd.Series, n) -> pd.Series:
    n = int(n)

    def calc(arr: np.ndarray) -> float:
        if len(arr) < n or np.isnan(arr).any():
            return np.nan
        x = np.arange(len(arr), dtype=float)
        return float(np.polyfit(x, arr, 1)[0])

    return series.rolling(n, min_periods=n).apply(calc, raw=True)


def _rsquare(series: pd.Series, n) -> pd.Series:
    n = int(n)

    def calc(arr: np.ndarray) -> float:
        if len(arr) < n or np.isnan(arr).any():
            return np.nan
        x = np.arange(len(arr), dtype=float)
        y = arr.astype(float)
        if np.std(y) == 0:
            return 0.0
        corr = np.corrcoef(x, y)[0, 1]
        return float(corr * corr)

    return series.rolling(n, min_periods=n).apply(calc, raw=True)


def _resi(series: pd.Series, n) -> pd.Series:
    n = int(n)

    def calc(arr: np.ndarray) -> float:
        if len(arr) < n or np.isnan(arr).any():
            return np.nan
        x = np.arange(len(arr), dtype=float)
        coef = np.polyfit(x, arr, 1)
        pred = coef[0] * x[-1] + coef[1]
        return float(arr[-1] - pred)

    return series.rolling(n, min_periods=n).apply(calc, raw=True)


def _quantile(series: pd.Series, n, q) -> pd.Series:
    n = int(n)
    q = float(q)
    return series.rolling(n, min_periods=n).quantile(q)


def _rank(series: pd.Series, n) -> pd.Series:
    n = int(n)

    def calc(arr: np.ndarray) -> float:
        if len(arr) < n or np.isnan(arr).any():
            return np.nan
        last = arr[-1]
        return float(np.sum(arr <= last) / len(arr))

    return series.rolling(n, min_periods=n).apply(calc, raw=True)


def _idxmax(series: pd.Series, n) -> pd.Series:
    n = int(n)

    def calc(arr: np.ndarray) -> float:
        if len(arr) < n or np.isnan(arr).any():
            return np.nan
        return float((len(arr) - 1 - int(np.argmax(arr))) / n)

    return series.rolling(n, min_periods=n).apply(calc, raw=True)


def _idxmin(series: pd.Series, n) -> pd.Series:
    n = int(n)

    def calc(arr: np.ndarray) -> float:
        if len(arr) < n or np.isnan(arr).any():
            return np.nan
        return float((len(arr) - 1 - int(np.argmin(arr))) / n)

    return series.rolling(n, min_periods=n).apply(calc, raw=True)


def _prepare_expression(expr: str) -> str:
    prepared = expr
    for field in _DOLLAR_FIELDS:
        prepared = prepared.replace(f"${field}", field)
    return prepared


def evaluate_expression(expr: str, data: pd.DataFrame) -> pd.Series:
    """对单标的 OHLCV DataFrame 计算 qlib 表达式（按 trade_date 索引）。"""
    df = data.sort_index()
    close = df["close"].astype(float)
    open_ = df["open"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    volume = df["volume"].astype(float)
    if "vwap" in df.columns:
        vwap = df["vwap"].astype(float)
    elif "amount" in df.columns and volume.gt(0).any():
        vwap = (df["amount"].astype(float) / volume.replace(0, np.nan)).ffill().bfill()
    else:
        vwap = (high + low + close) / 3.0

    namespace = {
        "close": close,
        "open": open_,
        "high": high,
        "low": low,
        "volume": volume,
        "vwap": vwap,
        "Ref": _ref,
        "Mean": _mean,
        "Std": _std,
        "Sum": _sum,
        "Max": _max,
        "Min": _min,
        "Abs": _abs,
        "Log": _log,
        "Greater": _greater,
        "Less": _less,
        "Corr": _corr,
        "Slope": _slope,
        "Rsquare": _rsquare,
        "Resi": _resi,
        "Quantile": _quantile,
        "Rank": _rank,
        "IdxMax": _idxmax,
        "IdxMin": _idxmin,
        "np": np,
    }

    prepared = _prepare_expression(expr)
    try:
        result = eval(prepared, {"__builtins__": {}}, namespace)  # noqa: S307
    except Exception as exc:
        raise ValueError(f"表达式求值失败: {expr}") from exc

    if isinstance(result, (int, float, np.floating)):
        return pd.Series(float(result), index=df.index)
    if isinstance(result, pd.Series):
        return result
    if isinstance(result, np.ndarray):
        return pd.Series(result, index=df.index)
    raise ValueError(f"表达式结果类型无效: {type(result)}")


def required_lookback(expr: str) -> int:
    """估算表达式所需历史 K 线长度。"""
    nums = [int(x) for x in re.findall(r"\b(\d+)\b", expr)]
    return max([60, *nums]) + 5 if nums else 65
