from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any

import numpy as np
import pandas as pd


def _sanitize(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (np.floating, float)):
        if np.isnan(value) or np.isinf(value):
            return None
        return float(value)
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, list):
        return [_sanitize(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _sanitize(v) for k, v in value.items()}
    return value


def df_to_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df is None or df.empty:
        return []
    records = df.replace({np.nan: None}).to_dict(orient="records")
    return [_sanitize(row) for row in records]


def to_json(obj: Any) -> Any:
    if is_dataclass(obj):
        return _sanitize(asdict(obj))
    if isinstance(obj, pd.DataFrame):
        return df_to_records(obj)
    if isinstance(obj, list):
        return [_sanitize(to_json(x) if is_dataclass(x) else x) for x in obj]
    return _sanitize(obj)
