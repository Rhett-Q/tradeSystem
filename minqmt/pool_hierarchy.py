from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

PoolLevel = Literal[1, 2, 3]
PoolKind = Literal["candidate", "tradable"]


@dataclass(frozen=True)
class PoolNode:
    """股票池层级节点。"""

    id: str
    label: str
    level: PoolLevel
    parent_id: str | None
    kind: PoolKind | None = None
    sector: str | None = None
    index_code: str | None = None
    description: str = ""


# L1：候选股票池（筛选宇宙）| 可交易池（通过风控、可下单）
# L2：指数 / 行业 / 策略分组
# L3：子池
POOL_HIERARCHY: list[PoolNode] = [
    # ── L1 ──
    PoolNode(
        "candidate",
        "候选股票池",
        1,
        None,
        kind="candidate",
        description="初选宇宙：指数/板块成分，供标签筛选",
    ),
    PoolNode(
        "tradable",
        "可交易池",
        1,
        None,
        kind="tradable",
        description="通过标签+风控后可下单标的",
    ),
    # ── L2 候选：按来源 ──
    PoolNode("cand_index", "宽基指数", 2, "candidate", kind="candidate"),
    PoolNode("cand_industry", "行业板块", 2, "candidate", kind="candidate"),
    PoolNode("cand_watch", "观察列表", 2, "candidate", kind="candidate"),
    # ── L3 候选：宽基 ──
    PoolNode("hs300", "沪深300", 3, "cand_index", kind="candidate", sector="沪深300", index_code="000300"),
    PoolNode("zz500", "中证500", 3, "cand_index", kind="candidate", sector="中证500", index_code="000905"),
    PoolNode("sz50", "上证50", 3, "cand_index", kind="candidate", sector="上证50", index_code="000016"),
    # ── L3 候选：行业 ──
    PoolNode("sw_pharma", "医药生物", 3, "cand_industry", kind="candidate", sector="SW1医药生物"),
    PoolNode("sw_electronics", "电子", 3, "cand_industry", kind="candidate", sector="SW1电子"),
    PoolNode("sw_food", "食品饮料", 3, "cand_industry", kind="candidate", sector="SW1食品饮料"),
    # ── L3 候选：观察 ──
    PoolNode("watchlist", "自选观察", 3, "cand_watch", kind="candidate"),
    # ── L2 可交易：按用途 ──
    PoolNode("trade_strategy", "策略池", 2, "tradable", kind="tradable", description="标签规则命中"),
    PoolNode("trade_position", "持仓池", 2, "tradable", kind="tradable", description="当前策略持仓"),
    PoolNode("trade_signal", "今日信号", 2, "tradable", kind="tradable", description="当日新生成信号"),
    # ── L3 可交易：策略子池 ──
    PoolNode("trade_momentum", "动量策略", 3, "trade_strategy", kind="tradable", description="20日动量 > 10%"),
    PoolNode("trade_lowvol", "低波策略", 3, "trade_strategy", kind="tradable", description="低波动+高流动性"),
    PoolNode("trade_core", "核心持仓", 3, "trade_position", kind="tradable"),
    PoolNode("trade_satellite", "卫星持仓", 3, "trade_position", kind="tradable"),
    PoolNode("trade_today", "当日新开", 3, "trade_signal", kind="tradable"),
]

SUBPOOL_SYMBOLS: dict[str, list[str]] = {
    # 候选
    "hs300": ["600519", "300750", "601318", "600036", "688981", "300760", "600276", "601899", "002594"],
    "zz500": ["002371", "688256", "601012", "688111", "603799"],
    "sz50": ["600519", "601318", "600036", "300750"],
    "sw_pharma": ["600276", "300760"],
    "sw_electronics": ["688981", "002371", "301308"],
    "sw_food": ["600519", "600887"],
    "watchlist": ["601166", "301308"],
    "cand_index": [],
    "cand_industry": [],
    "cand_watch": [],
    "candidate": [],
    # 可交易（候选的子集，需 non_st + trading + 策略标签）
    "trade_momentum": ["300033", "688256", "300750"],
    "trade_lowvol": ["601318", "600036", "600887"],
    "trade_core": ["600519", "300750"],
    "trade_satellite": ["002594", "688981"],
    "trade_today": ["688981"],
    "trade_strategy": [],
    "trade_position": [],
    "trade_signal": [],
    "tradable": [],
}


@dataclass
class PoolHierarchy:
    """股票池层级树操作。"""

    nodes: list[PoolNode] = field(default_factory=lambda: list(POOL_HIERARCHY))
    subpool_symbols: dict[str, list[str]] = field(default_factory=lambda: dict(SUBPOOL_SYMBOLS))

    def get_node(self, node_id: str) -> PoolNode | None:
        return next((n for n in self.nodes if n.id == node_id), None)

    def get_children(self, parent_id: str | None) -> list[PoolNode]:
        return [n for n in self.nodes if n.parent_id == parent_id]

    def get_kind(self, node_id: str) -> PoolKind | None:
        for node in self.get_path(node_id):
            if node.kind:
                return node.kind
        return None

    def get_path(self, node_id: str) -> list[PoolNode]:
        path: list[PoolNode] = []
        current = self.get_node(node_id)
        while current:
            path.insert(0, current)
            current = self.get_node(current.parent_id) if current.parent_id else None
        return path

    def path_label(self, node_id: str, sep: str = " › ") -> str:
        return sep.join(n.label for n in self.get_path(node_id))

    def resolve_symbols(self, node_id: str) -> list[str]:
        node = self.get_node(node_id)
        if not node:
            return []

        if node_id in self.subpool_symbols and self.subpool_symbols[node_id]:
            return list(self.subpool_symbols[node_id])

        children = self.get_children(node_id)
        if children:
            symbols: list[str] = []
            for child in children:
                symbols.extend(self.resolve_symbols(child.id))
            return list(dict.fromkeys(symbols))

        return list(self.subpool_symbols.get(node_id, []))

    def promote_to_tradable(
        self,
        symbols: list[str],
        target_node: str = "trade_momentum",
    ) -> list[str]:
        """将候选标的调入可交易池（示例：写入子池映射）。"""
        if target_node not in self.subpool_symbols:
            self.subpool_symbols[target_node] = []
        existing = set(self.subpool_symbols[target_node])
        added = [s for s in symbols if s not in existing]
        self.subpool_symbols[target_node] = list(existing | set(symbols))
        return added

    def list_flat(self) -> list[dict[str, str | int | None]]:
        return [
            {
                "id": n.id,
                "label": n.label,
                "level": n.level,
                "kind": n.kind or self.get_kind(n.id),
                "parent_id": n.parent_id,
                "path": self.path_label(n.id),
                "count": len(self.resolve_symbols(n.id)),
            }
            for n in self.nodes
        ]
