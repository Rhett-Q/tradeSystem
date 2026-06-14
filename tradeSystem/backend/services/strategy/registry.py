from __future__ import annotations

from typing import Any, Callable

from services.strategy.strategies.ma_crossover import MACrossOver
from services.strategy.strategies.macd_crossover import MACDCrossOver
from services.strategy.strategies.multi_factor import MultiFactorStrategy
from services.strategy.strategies.rsi_reversal import RSIReversal

ParamSpec = dict[str, Any]
StrategySpec = dict[str, Any]

STRATEGY_REGISTRY: dict[str, StrategySpec] = {
    "ma_crossover": {
        "class": MACrossOver,
        "name": "均线交叉",
        "category": "trend",
        "tags": ["趋势", "经典", "Backtrader"],
        "description": "快慢均线金叉/死叉的全仓进出策略。",
        "logic": (
            "买入：快均线上穿慢均线（金叉）。\n"
            "卖出：快均线下穿慢均线（死叉）。\n"
            "持仓：全仓买入，卖出时清仓。"
        ),
        "indicators": ["SMA(快)", "SMA(慢)"],
        "suitable": "趋势较明显的单边行情。",
        "risk": "震荡市中金叉死叉频繁，可能连续小亏。",
        "params": [
            {
                "key": "fast",
                "label": "快线周期",
                "type": "int",
                "default": 5,
                "min": 2,
                "max": 120,
            },
            {
                "key": "slow",
                "label": "慢线周期",
                "type": "int",
                "default": 20,
                "min": 3,
                "max": 250,
            },
        ],
    },
    "rsi_reversal": {
        "class": RSIReversal,
        "name": "RSI 反转",
        "category": "momentum",
        "tags": ["超买超卖", "震荡"],
        "description": "RSI 进入超卖区买入，进入超买区卖出。",
        "logic": (
            "买入：RSI 低于超卖阈值（默认 30）。\n"
            "卖出：RSI 高于超买阈值（默认 70）。\n"
            "适合捕捉超卖反弹与超买回落。"
        ),
        "indicators": ["RSI"],
        "suitable": "区间波动、反弹型行情。",
        "risk": "强趋势中 RSI 可能长期超买/超卖，导致逆势持仓。",
        "params": [
            {
                "key": "period",
                "label": "RSI 周期",
                "type": "int",
                "default": 14,
                "min": 5,
                "max": 60,
            },
            {
                "key": "oversold",
                "label": "超卖线",
                "type": "int",
                "default": 30,
                "min": 10,
                "max": 45,
            },
            {
                "key": "overbought",
                "label": "超买线",
                "type": "int",
                "default": 70,
                "min": 55,
                "max": 90,
            },
        ],
    },
    "macd_crossover": {
        "class": MACDCrossOver,
        "name": "MACD 交叉",
        "category": "trend",
        "tags": ["MACD", "趋势"],
        "description": "MACD 线与信号线金叉买入、死叉卖出。",
        "logic": (
            "买入：MACD 线上穿信号线。\n"
            "卖出：MACD 线下穿信号线。\n"
            "经典趋势动量指标组合。"
        ),
        "indicators": ["MACD", "Signal"],
        "suitable": "中期趋势跟踪。",
        "risk": "参数敏感；滞后于价格拐点。",
        "params": [
            {
                "key": "fast",
                "label": "快线 EMA",
                "type": "int",
                "default": 12,
                "min": 5,
                "max": 30,
            },
            {
                "key": "slow",
                "label": "慢线 EMA",
                "type": "int",
                "default": 26,
                "min": 10,
                "max": 60,
            },
            {
                "key": "signal",
                "label": "信号线",
                "type": "int",
                "default": 9,
                "min": 3,
                "max": 20,
            },
        ],
    },
    "multi_factor": {
        "class": MultiFactorStrategy,
        "name": "多因子组合",
        "category": "composite",
        "tags": ["Alpha158", "多因子", "AND"],
        "uses_conditions": True,
        "description": "多个 Alpha158 因子同时满足时买入，任一不满足时卖出。",
        "logic": (
            "买入：全部因子条件在同一交易日满足（AND）。\n"
            "卖出：任一因子条件不满足时清仓。\n"
            "与「多因子选股」使用相同的因子表达式与阈值语义。"
        ),
        "indicators": ["Alpha158 因子"],
        "suitable": "有明确因子逻辑的单标的策略验证。",
        "risk": "因子失效或过度拟合时信号稀疏或频繁；需足够历史数据计算因子。",
        "params": [],
    },
}

_PARAM_VALIDATORS: dict[str, Callable[[dict[str, Any]], None]] = {}


def _validate_ma_crossover(params: dict[str, Any]) -> None:
    if params["fast"] >= params["slow"]:
        raise ValueError("快线周期必须小于慢线周期")


def _validate_rsi(params: dict[str, Any]) -> None:
    if params["oversold"] >= params["overbought"]:
        raise ValueError("超卖线必须小于超买线")


def _validate_macd(params: dict[str, Any]) -> None:
    if params["fast"] >= params["slow"]:
        raise ValueError("MACD 快线周期必须小于慢线周期")


_PARAM_VALIDATORS["ma_crossover"] = _validate_ma_crossover
_PARAM_VALIDATORS["rsi_reversal"] = _validate_rsi
_PARAM_VALIDATORS["macd_crossover"] = _validate_macd


def _default_params(spec: StrategySpec) -> dict[str, Any]:
    return {p["key"]: p["default"] for p in spec["params"]}


def _public_summary(strategy_id: str, spec: StrategySpec) -> dict[str, Any]:
    return {
        "id": strategy_id,
        "name": spec["name"],
        "category": spec["category"],
        "tags": spec.get("tags", []),
        "description": spec["description"],
        "params": spec["params"],
        "default_params": _default_params(spec),
        "indicators": spec.get("indicators", []),
        "uses_conditions": spec.get("uses_conditions", False),
    }


def list_strategies(*, category: str = "") -> list[dict[str, Any]]:
    items = [_public_summary(k, v) for k, v in STRATEGY_REGISTRY.items()]
    if category:
        items = [s for s in items if s["category"] == category]
    return sorted(items, key=lambda x: (x["category"], x["id"]))


def get_strategy_detail(strategy_id: str) -> dict[str, Any]:
    spec = STRATEGY_REGISTRY.get(strategy_id)
    if not spec:
        raise ValueError(f"未知策略: {strategy_id}")
    detail = _public_summary(strategy_id, spec)
    detail.update(
        {
            "logic": spec.get("logic", ""),
            "suitable": spec.get("suitable", ""),
            "risk": spec.get("risk", ""),
            "uses_conditions": spec.get("uses_conditions", False),
        },
    )
    return detail


def get_strategy_class(strategy_id: str) -> tuple[type, StrategySpec]:
    spec = STRATEGY_REGISTRY.get(strategy_id)
    if not spec:
        raise ValueError(f"未知策略: {strategy_id}")
    return spec["class"], spec


def validate_params(strategy_id: str, params: dict[str, Any] | None) -> dict[str, Any]:
    _, spec = get_strategy_class(strategy_id)
    validated: dict[str, Any] = {}
    for p in spec["params"]:
        key = p["key"]
        raw = (params or {}).get(key, p["default"])
        if p["type"] == "int":
            val = int(raw)
            val = max(int(p["min"]), min(int(p["max"]), val))
        else:
            val = float(raw)
            val = max(float(p["min"]), min(float(p["max"]), val))
        validated[key] = val

    validator = _PARAM_VALIDATORS.get(strategy_id)
    if validator:
        validator(validated)
    return validated
