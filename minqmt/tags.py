from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Literal

import pandas as pd

TagCategory = Literal["行情", "板块", "基础", "财务", "实时"]


@dataclass
class TagRule:
    """基于 MiniQMT 可获取字段的标签规则定义。"""

    id: str
    name: str
    category: TagCategory
    source_api: str
    source_fields: list[str]
    rule_expr: str
    description: str
    enabled: bool = True


# 内置标签：每条规则对应 xtquant 实际可拉取的字段
DEFAULT_TAG_RULES: list[TagRule] = [
    TagRule(
        id="momentum_20d",
        name="20日动量",
        category="行情",
        source_api="get_market_data_ex",
        source_fields=["close"],
        rule_expr="close[-1]/close[-21]-1 > 0.10",
        description="近 20 个交易日涨幅 > 10%（由 K 线 close 计算）",
    ),
    TagRule(
        id="high_amount",
        name="高成交额",
        category="行情",
        source_api="get_market_data_ex",
        source_fields=["amount"],
        rule_expr="amount[-1] > 2e8",
        description="最新一日成交额 > 2 亿元",
    ),
    TagRule(
        id="volume_surge",
        name="放量",
        category="行情",
        source_api="get_market_data_ex",
        source_fields=["volume"],
        rule_expr="volume[-1] > mean(volume[-6:-1]) * 1.5",
        description="当日成交量 > 近 5 日均量 1.5 倍",
    ),
    TagRule(
        id="limit_up",
        name="涨停",
        category="行情",
        source_api="get_market_data_ex",
        source_fields=["close", "high"],
        rule_expr="(close[-1]/preClose[-1]-1) >= 0.095",
        description="收盘价接近涨停（需配合 preClose 或 tick）",
    ),
    TagRule(
        id="low_volatility",
        name="低波动",
        category="行情",
        source_api="get_market_data_ex",
        source_fields=["close"],
        rule_expr="std(pct_change(close[-60:])) * sqrt(252) < 0.25",
        description="60 日年化波动率 < 25%",
    ),
    TagRule(
        id="hs300",
        name="沪深300",
        category="板块",
        source_api="get_stock_list_in_sector",
        source_fields=["sector=沪深300"],
        rule_expr="symbol in sector('沪深300')",
        description="属于沪深300 板块成分",
    ),
    TagRule(
        id="zz500",
        name="中证500",
        category="板块",
        source_api="get_stock_list_in_sector",
        source_fields=["sector=中证500"],
        rule_expr="symbol in sector('中证500')",
        description="属于中证500 板块成分",
    ),
    TagRule(
        id="non_st",
        name="非ST",
        category="基础",
        source_api="get_instrument_detail",
        source_fields=["InstrumentName", "InstrumentStatus"],
        rule_expr="'ST' not in InstrumentName",
        description="合约名称不含 ST/*ST",
    ),
    TagRule(
        id="trading",
        name="正常交易",
        category="基础",
        source_api="get_instrument_detail",
        source_fields=["IsTrading"],
        rule_expr="IsTrading == 1",
        description="instrument_detail.IsTrading 为 1",
    ),
    TagRule(
        id="high_roe",
        name="高ROE",
        category="财务",
        source_api="get_financial_data",
        source_fields=["PershareIndex.roe"],
        rule_expr="roe > 0.15",
        description="最新 PershareIndex ROE > 15%（需 download_financial_data2）",
    ),
    TagRule(
        id="tick_active",
        name="盘口活跃",
        category="实时",
        source_api="get_full_tick",
        source_fields=["volume", "amount", "bidPrice1", "askPrice1"],
        rule_expr="amount > 1e8 and (askPrice1-bidPrice1)/lastPrice < 0.002",
        description="tick 快照：成交额 > 1 亿且买卖价差 < 0.2%",
    ),
]


@dataclass
class TagEngine:
    """根据 MiniQMT 快照数据为标的打标签。"""

    rules: list[TagRule] = field(default_factory=lambda: list(DEFAULT_TAG_RULES))

    def evaluate_snapshot(self, row: dict[str, Any]) -> list[str]:
        """对 fetch_pool_snapshot 单行结果评估标签。"""
        tags: list[str] = []
        for rule in self.rules:
            if not rule.enabled:
                continue
            if self._match(rule, row):
                tags.append(rule.id)
        return tags

    def evaluate_batch(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        out["tags"] = out.apply(lambda r: self.evaluate_snapshot(r.to_dict()), axis=1)
        return out

    @staticmethod
    def _match(rule: TagRule, row: dict[str, Any]) -> bool:
        checks: dict[str, Callable[[dict[str, Any]], bool]] = {
            "momentum_20d": lambda r: float(r.get("momentum_20d", 0)) > 10,
            "high_amount": lambda r: float(r.get("amount", 0)) > 2e8,
            "volume_surge": lambda r: bool(r.get("volume_surge")),
            "limit_up": lambda r: bool(r.get("limit_up")),
            "low_volatility": lambda r: bool(r.get("low_volatility")),
            "hs300": lambda r: r.get("pool") == "hs300" or "hs300" in r.get("sectors", []),
            "zz500": lambda r: r.get("pool") == "zz500" or "zz500" in r.get("sectors", []),
            "non_st": lambda r: "ST" not in str(r.get("name", "")).upper(),
            "trading": lambda r: r.get("is_trading", True) is not False,
            "high_roe": lambda r: float(r.get("roe", 0)) > 0.15,
            "tick_active": lambda r: bool(r.get("tick_active")),
        }
        fn = checks.get(rule.id)
        return fn(row) if fn else False
