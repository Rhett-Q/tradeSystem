from __future__ import annotations

import backtrader as bt


class EquityCurveAnalyzer(bt.Analyzer):
    """记录每个 bar 的账户净值。"""

    def __init__(self) -> None:
        self.curve: list[dict] = []

    def next(self) -> None:
        dt = self.strategy.data.datetime.date(0)
        self.curve.append(
            {
                "date": dt.isoformat(),
                "value": round(float(self.strategy.broker.getvalue()), 2),
            },
        )

    def get_analysis(self) -> list[dict]:
        return self.curve


class TradeListAnalyzer(bt.Analyzer):
    """记录已平仓交易明细。"""

    def __init__(self) -> None:
        self.trades: list[dict] = []

    def notify_trade(self, trade: bt.Trade) -> None:
        if not trade.isclosed:
            return
        cost = abs(float(trade.price) * float(trade.size)) or 1.0
        self.trades.append(
            {
                "open_date": bt.num2date(trade.dtopen).strftime("%Y-%m-%d"),
                "close_date": bt.num2date(trade.dtclose).strftime("%Y-%m-%d"),
                "size": int(trade.size),
                "price": round(float(trade.price), 4),
                "pnl": round(float(trade.pnlcomm), 2),
                "return_pct": round(float(trade.pnlcomm) / cost * 100, 2),
            },
        )

    def get_analysis(self) -> list[dict]:
        return self.trades


class OrderSignalAnalyzer(bt.Analyzer):
    """记录每笔成交的买/卖信号，供 K 线标记。"""

    def __init__(self) -> None:
        self.signals: list[dict] = []

    def notify_order(self, order: bt.Order) -> None:
        if order.status != order.Completed:
            return
        side = "buy" if order.isbuy() else "sell"
        self.signals.append(
            {
                "date": bt.num2date(order.executed.dt).strftime("%Y-%m-%d"),
                "side": side,
                "price": round(float(order.executed.price), 4),
                "size": int(abs(order.executed.size)),
            },
        )

    def get_analysis(self) -> list[dict]:
        return self.signals
