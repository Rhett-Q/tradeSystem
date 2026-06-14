from __future__ import annotations

import backtrader as bt


class MACrossOver(bt.Strategy):
    """快均线上穿慢均线买入，下穿卖出。"""

    params = (
        ("fast", 5),
        ("slow", 20),
    )

    def __init__(self) -> None:
        self.ma_fast = bt.ind.SMA(self.data.close, period=self.p.fast)
        self.ma_slow = bt.ind.SMA(self.data.close, period=self.p.slow)
        self.crossover = bt.ind.CrossOver(self.ma_fast, self.ma_slow)

    def next(self) -> None:
        if not self.position and self.crossover > 0:
            self.buy()
        elif self.position and self.crossover < 0:
            self.close()
