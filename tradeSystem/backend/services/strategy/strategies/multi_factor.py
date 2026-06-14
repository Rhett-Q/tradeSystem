from __future__ import annotations

import backtrader as bt


class MultiFactorStrategy(bt.Strategy):
    """多因子 AND 信号：signal=1 买入/持有，signal=0 卖出。"""

    def next(self) -> None:
        active = float(self.data.signal[0]) > 0.5
        if active and not self.position:
            self.buy()
        elif not active and self.position:
            self.close()
