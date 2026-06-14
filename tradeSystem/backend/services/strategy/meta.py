from __future__ import annotations

CATEGORY_LABELS: dict[str, str] = {
    "trend": "趋势跟踪",
    "momentum": "动量反转",
    "composite": "组合策略",
}

CATEGORY_HELP: dict[str, str] = {
    "trend": "跟随价格趋势，适合单边行情；震荡市可能频繁交易。",
    "momentum": "基于超买超卖或动量拐点，适合区间波动与反弹。",
    "composite": "多指标组合，降低单一信号误判。",
}
