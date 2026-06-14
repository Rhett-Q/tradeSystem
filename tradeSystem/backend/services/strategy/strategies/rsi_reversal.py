from __future__ import annotations

import backtrader as bt


class RSIReversal(bt.Strategy):
    """RSI 超卖买入、超买卖出。"""

    params = (
        ("period", 14),
        ("oversold", 30),
        ("overbought", 70),
    )

    def __init__(self) -> None:
        self.rsi = bt.ind.RSI(self.data.close, period=self.p.period)

    def next(self) -> None:
        if not self.position and self.rsi[0] < self.p.oversold:
            self.buy()
        elif self.position and self.rsi[0] > self.p.overbought:
            self.close()
