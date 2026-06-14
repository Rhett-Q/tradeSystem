from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Literal

import pandas as pd

from minqmt.fetcher import MinQmtDataFetcher
from minqmt.filter_expr import FILTER_FIELD_DOCS, FilterExprError, eval_filter_expr, new_filter_id, validate_filter_expr
from minqmt.tags import TagEngine

WatchStatus = Literal["watching", "triggered", "expired"]
TriggerType = Literal["momentum", "volume", "ma_cross", "price_break"]


@dataclass
class FilterRule:
    """筛选条件：内置或用户自定义。"""

    id: str
    name: str
    enabled: bool
    expr: str
    description: str
    builtin: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "enabled": self.enabled,
            "expr": self.expr,
            "description": self.description,
            "builtin": self.builtin,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FilterRule:
        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            enabled=bool(data.get("enabled", True)),
            expr=str(data["expr"]),
            description=str(data.get("description", "")),
            builtin=bool(data.get("builtin", False)),
        )


@dataclass
class TriggerRule:
    id: str
    name: str
    trigger_type: TriggerType
    params: dict[str, Any]
    description: str


DEFAULT_FILTERS: list[FilterRule] = [
    FilterRule("non_st", "非 ST", True, "non_st", "名称不含 ST", builtin=True),
    FilterRule("trading", "正常交易", True, "is_trading", "IsTrading == 1", builtin=True),
    FilterRule("liquidity", "成交额 > 2亿", True, "amount > 2e8", "成交额 > 2 亿", builtin=True),
    FilterRule("momentum_min", "20日动量 > 0", True, "momentum_20d > 0", "20 日涨幅 > 0", builtin=True),
]

DEFAULT_TRIGGERS: list[TriggerRule] = [
    TriggerRule("mom10", "动量突破", "momentum", {"threshold": 10}, "20日动量 > 10%"),
    TriggerRule("vol_surge", "放量确认", "volume", {"ratio": 1.5}, "成交量 > 5 日均量 1.5 倍"),
    TriggerRule("ma_cross", "均线金叉", "ma_cross", {"fast": 5, "slow": 20}, "MA5 上穿 MA20"),
    TriggerRule("break_high", "突破前高", "price_break", {"days": 20}, "收盘价创 20 日新高"),
]


@dataclass
class WatchItem:
    symbol: str
    name: str
    added_at: str
    status: WatchStatus
    trigger_id: str
    trigger_progress: float
    trigger_label: str
    close: float
    momentum20d: float
    amount: float
    tag_ids: list[str] = field(default_factory=list)


@dataclass
class MarketScreener:
    """全市场筛选 → 观察池 → 触发检测。"""

    fetcher: MinQmtDataFetcher = field(default_factory=MinQmtDataFetcher)
    tag_engine: TagEngine = field(default_factory=TagEngine)
    filters: list[FilterRule] = field(default_factory=lambda: [replace(r) for r in DEFAULT_FILTERS])
    triggers: list[TriggerRule] = field(default_factory=lambda: list(DEFAULT_TRIGGERS))

    def list_filters(self) -> list[FilterRule]:
        return list(self.filters)

    def get_filter(self, filter_id: str) -> FilterRule | None:
        return next((f for f in self.filters if f.id == filter_id), None)

    def set_filter_enabled(self, filter_id: str, enabled: bool) -> None:
        rule = self.get_filter(filter_id)
        if rule:
            rule.enabled = enabled

    def add_custom_filter(
        self,
        name: str,
        expr: str,
        description: str = "",
        *,
        enabled: bool = True,
    ) -> FilterRule:
        ok, msg = validate_filter_expr(expr)
        if not ok:
            raise FilterExprError(msg)
        rule = FilterRule(
            id=new_filter_id(),
            name=name,
            enabled=enabled,
            expr=expr.strip(),
            description=description or f"自定义: {expr.strip()}",
            builtin=False,
        )
        self.filters.append(rule)
        return rule

    def update_filter(
        self,
        filter_id: str,
        *,
        name: str | None = None,
        expr: str | None = None,
        description: str | None = None,
        enabled: bool | None = None,
    ) -> FilterRule:
        rule = self.get_filter(filter_id)
        if not rule:
            raise KeyError(f"规则不存在: {filter_id}")

        new_expr = expr.strip() if expr is not None else rule.expr
        if expr is not None:
            ok, msg = validate_filter_expr(new_expr)
            if not ok:
                raise FilterExprError(msg)

        if expr is not None and rule.builtin:
            # 内置规则允许改表达式副本（视为用户覆盖）
            pass

        updated = FilterRule(
            id=rule.id,
            name=name if name is not None else rule.name,
            enabled=enabled if enabled is not None else rule.enabled,
            expr=new_expr,
            description=description if description is not None else rule.description,
            builtin=rule.builtin,
        )
        idx = self.filters.index(rule)
        self.filters[idx] = updated
        return updated

    def remove_filter(self, filter_id: str) -> None:
        rule = self.get_filter(filter_id)
        if not rule:
            raise KeyError(f"规则不存在: {filter_id}")
        if rule.builtin:
            raise FilterExprError("内置规则不可删除，可禁用或编辑表达式")
        self.filters = [f for f in self.filters if f.id != filter_id]

    def load_custom_filters(self, rules: list[dict[str, Any]]) -> None:
        """从 JSON/dict 列表加载自定义规则（保留内置规则）。"""
        builtins = [f for f in self.filters if f.builtin]
        custom = []
        for raw in rules:
            rule = FilterRule.from_dict(raw)
            if rule.builtin:
                continue
            ok, _ = validate_filter_expr(rule.expr)
            if ok:
                custom.append(rule)
        self.filters = builtins + custom

    def export_custom_filters(self) -> list[dict[str, Any]]:
        return [f.to_dict() for f in self.filters if not f.builtin]

    @staticmethod
    def available_fields() -> dict[str, str]:
        return dict(FILTER_FIELD_DOCS)

    def run_screen(
        self,
        universe: list[str],
        *,
        bar_count: int = 21,
    ) -> pd.DataFrame:
        snapshot = self.fetcher.fetch_pool_snapshot(
            universe,
            bar_count=bar_count,
            download=False,
        )
        if snapshot.empty:
            return snapshot

        tagged = self.tag_engine.evaluate_batch(snapshot)
        rows: list[dict[str, Any]] = []
        for _, row in tagged.iterrows():
            item = row.to_dict()
            if self._passes_filters(item):
                rows.append(item)
        return pd.DataFrame(rows)

    def evaluate_triggers(self, items: list[WatchItem]) -> list[WatchItem]:
        out: list[WatchItem] = []
        for item in items:
            updated = item
            if item.trigger_id == "mom10":
                threshold = 10.0
                progress = min(100.0, item.momentum20d / threshold * 100)
                if item.momentum20d >= threshold:
                    updated = WatchItem(
                        **{
                            **item.__dict__,
                            "status": "triggered",
                            "trigger_progress": 100,
                            "trigger_label": "已触发 · 动量突破",
                        },
                    )
                else:
                    updated = WatchItem(
                        **{
                            **item.__dict__,
                            "status": "watching",
                            "trigger_progress": progress,
                            "trigger_label": f"距动量 10% 还差 {threshold - item.momentum20d:.1f}%",
                        },
                    )
            out.append(updated)
        return out

    def _passes_filters(self, row: dict[str, Any]) -> bool:
        for rule in self.filters:
            if not rule.enabled:
                continue
            try:
                if not eval_filter_expr(rule.expr, row):
                    return False
            except FilterExprError:
                return False
        return True
