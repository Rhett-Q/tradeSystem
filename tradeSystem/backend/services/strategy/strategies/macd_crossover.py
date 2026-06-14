from __future__ import annotations

import backtrader as bt


class MACDCrossOver(bt.Strategy):
    """MACD 线上穿信号线买入，下穿卖出。"""

    params = (
        ("fast", 12),
        ("slow", 26),
        ("signal", 9),
    )

    def __init__(self) -> None:
        self.macd = bt.ind.MACD(
            self.data.close,
            period_me1=self.p.fast,
            period_me2=self.p.slow,
            period_signal=self.p.signal,
        )
        self.crossover = bt.ind.CrossOver(self.macd.macd, self.macd.signal)

    def next(self) -> None:
        if not self.position and self.crossover > 0:
            self.buy()
        elif self.position and self.crossover < 0:
            self.close()
