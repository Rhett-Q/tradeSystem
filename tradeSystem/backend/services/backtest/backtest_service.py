from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import backtrader as bt

_WORKSPACE = Path(__file__).resolve().parents[4]
if str(_WORKSPACE) not in sys.path:
    sys.path.insert(0, str(_WORKSPACE))

from minqmt.symbols import to_xt_symbol

from db.repositories import symbols as symbol_repo
from services.backtest.analyzers import EquityCurveAnalyzer, OrderSignalAnalyzer, TradeListAnalyzer
from services.backtest.data_loader import bars_to_dataframe, load_daily_bars, make_pandas_feed
from services.strategy.registry import get_strategy_class, validate_params
from services.screener_log import ScreenLogger


def _safe_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _validate_params(strategy_id: str, params: dict[str, Any]) -> dict[str, Any]:
    return validate_params(strategy_id, params)


def run_backtest(
    *,
    symbol: str,
    strategy: str = "ma_crossover",
    params: dict[str, Any] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    initial_cash: float = 100_000.0,
    commission: float = 0.001,
    stake_pct: float = 95.0,
) -> dict[str, Any]:
    log = ScreenLogger("backtest")
    xt_symbol = to_xt_symbol(symbol)
    meta = symbol_repo.get_symbol(xt_symbol) or {}
    strategy_params = _validate_params(strategy, params or {})

    log.info(f"加载 {xt_symbol} 日 K 数据…")
    bars = load_daily_bars(xt_symbol, start_date, end_date)
    if not bars:
        raise ValueError(f"{xt_symbol} 在指定区间无有效日 K 数据，请先同步日线")

    min_bars = max(strategy_params.values()) + 5 if strategy_params else 30
    if len(bars) < min_bars:
        raise ValueError(f"有效 K 线仅 {len(bars)} 根，至少需要 {min_bars} 根")

    log.info(f"共 {len(bars)} 根 K 线（{bars[0]['date']} ~ {bars[-1]['date']}）")
    df = bars_to_dataframe(bars)

    strat_cls, spec = get_strategy_class(strategy)
    cerebro = bt.Cerebro(stdstats=False)
    cerebro.broker.setcash(initial_cash)
    cerebro.broker.setcommission(commission=commission)
    cerebro.addsizer(bt.sizers.PercentSizer, percents=stake_pct)
    cerebro.adddata(make_pandas_feed(df))
    cerebro.addstrategy(strat_cls, **strategy_params)

    cerebro.addanalyzer(EquityCurveAnalyzer, _name="equity")
    cerebro.addanalyzer(TradeListAnalyzer, _name="trades")
    cerebro.addanalyzer(OrderSignalAnalyzer, _name="signals")
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name="drawdown")
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name="sharpe", riskfreerate=0.0)
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="trade_stats")

    log.info(f"运行策略「{spec['name']}」…")
    results = cerebro.run()
    strat = results[0]

    final_value = round(float(cerebro.broker.getvalue()), 2)
    total_return_pct = round((final_value - initial_cash) / initial_cash * 100, 2)

    dd = strat.analyzers.drawdown.get_analysis()
    max_drawdown_pct = round(_safe_float(dd.max.drawdown if dd.max else 0), 2)

    sharpe_analysis = strat.analyzers.sharpe.get_analysis()
    sharpe_ratio = sharpe_analysis.get("sharperatio")
    sharpe_ratio = round(_safe_float(sharpe_ratio), 3) if sharpe_ratio is not None else None

    ta = strat.analyzers.trade_stats.get_analysis()
    total_trades = int(ta.total.closed) if ta.total else 0
    won_trades = int(ta.won.total) if ta.won else 0
    win_rate_pct = round(won_trades / total_trades * 100, 1) if total_trades else 0.0

    equity_curve = strat.analyzers.equity.get_analysis()
    trades = strat.analyzers.trades.get_analysis()
    signals = strat.analyzers.signals.get_analysis()

    log.set_stat("bars", len(bars))
    log.set_stat("trades", total_trades)
    log.set_stat("signals", len(signals))
    log.finish(f"回测完成，总收益 {total_return_pct:+.2f}%")

    return log.attach(
        {
            "symbol": xt_symbol,
            "name": meta.get("name") or "",
            "sector": meta.get("sector") or "",
            "strategy": strategy,
            "strategy_name": spec["name"],
            "params": strategy_params,
            "period": "1d",
            "start_date": bars[0]["date"],
            "end_date": bars[-1]["date"],
            "bars": len(bars),
            "initial_cash": initial_cash,
            "commission": commission,
            "stake_pct": stake_pct,
            "metrics": {
                "total_return_pct": total_return_pct,
                "max_drawdown_pct": -abs(max_drawdown_pct),
                "sharpe": sharpe_ratio,
                "win_rate_pct": win_rate_pct,
                "total_trades": total_trades,
                "final_value": final_value,
            },
            "equity_curve": equity_curve,
            "trades": trades,
            "signals": signals,
            "rows": bars,
        },
    )
