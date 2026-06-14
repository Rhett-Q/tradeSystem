from __future__ import annotations

import math
import threading
import time
from typing import Any

import pandas as pd

from db.connection import get_cursor
from services.screener_filters import listed_symbol_where

_CACHE_LOCK = threading.Lock()
_PANEL_CACHE: dict[str, Any] = {"loaded_at": 0.0, "lookback": 0, "panel": None}
_CACHE_TTL_SEC = 300


def _load_panel_from_db(lookback_days: int) -> pd.DataFrame:
    with get_cursor() as cur:
        cur.execute(
            f"""
            SELECT
                k.symbol,
                k.trade_date,
                k.open,
                k.high,
                k.low,
                k.close,
                k.volume,
                k.amount
            FROM kline_daily k
            INNER JOIN symbols s ON s.symbol = k.symbol AND {listed_symbol_where("s")}
            WHERE k.close IS NOT NULL AND k.close > 0
              AND lower(k.close::text) <> 'nan'
              AND k.trade_date >= CURRENT_DATE - %s * INTERVAL '1 day'
            ORDER BY k.symbol, k.trade_date
            """,
            (lookback_days,),
        )
        rows = cur.fetchall()

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame([dict(r) for r in rows])
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    df["vwap"] = np_where_vwap(df)
    df = df.set_index(["symbol", "trade_date"]).sort_index()
    return df


def np_where_vwap(df: pd.DataFrame) -> pd.Series:
    import numpy as np

    vol = df["volume"].astype(float)
    amt = df["amount"].astype(float)
    fallback = (df["high"].astype(float) + df["low"].astype(float) + df["close"].astype(float)) / 3.0
    return np.where(vol > 0, amt / vol, fallback)


def get_panel(lookback_days: int) -> pd.DataFrame:
    now = time.time()
    with _CACHE_LOCK:
        cached = _PANEL_CACHE.get("panel")
        if (
            cached is not None
            and _PANEL_CACHE.get("lookback") == lookback_days
            and now - float(_PANEL_CACHE.get("loaded_at", 0)) < _CACHE_TTL_SEC
        ):
            return cached.copy()

    panel = _load_panel_from_db(lookback_days)
    with _CACHE_LOCK:
        _PANEL_CACHE["panel"] = panel
        _PANEL_CACHE["lookback"] = lookback_days
        _PANEL_CACHE["loaded_at"] = now
    return panel.copy()


def iter_symbol_frames(panel: pd.DataFrame) -> list[tuple[str, pd.DataFrame]]:
    if panel.empty:
        return []
    symbols = panel.index.get_level_values(0).unique()
    return [(str(sym), panel.xs(sym, level=0).copy()) for sym in symbols]
