from __future__ import annotations

from datetime import date

import backtrader as bt
import pandas as pd

from db.repositories import kline as kline_repo


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value[:10])


def load_daily_bars(
    symbol: str,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict]:
    return kline_repo.query_daily_range(
        symbol,
        start_date=_parse_date(start_date),
        end_date=_parse_date(end_date),
    )


def bars_to_dataframe(bars: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(bars)
    df["datetime"] = pd.to_datetime(df["date"])
    df = df.set_index("datetime")
    return df[["open", "high", "low", "close", "volume"]].astype(float)


def make_pandas_feed(df: pd.DataFrame) -> bt.feeds.PandasData:
    return bt.feeds.PandasData(
        dataname=df,
        datetime=None,
        open="open",
        high="high",
        low="low",
        close="close",
        volume="volume",
        openinterest=-1,
    )
