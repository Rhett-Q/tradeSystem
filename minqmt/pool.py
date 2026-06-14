from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from minqmt.fetcher import MinQmtDataFetcher
from minqmt.pool_hierarchy import PoolHierarchy, PoolNode
from minqmt.tags import TagEngine


# MiniQMT 板块/指数 → 构建股票池的数据源映射
POOL_SOURCES: dict[str, dict[str, str]] = {
    "hs300": {
        "label": "沪深300",
        "sector": "沪深300",
        "index_code": "000300",
    },
    "zz500": {
        "label": "中证500",
        "sector": "中证500",
        "index_code": "000905",
    },
    "sz50": {
        "label": "上证50",
        "sector": "上证50",
        "index_code": "000016",
    },
    "cyb": {
        "label": "创业板指",
        "sector": "创业板",
        "index_code": "399006",
    },
}


@dataclass
class StockPoolBuilder:
    """基于 MiniQMT 板块/指数接口构建股票池并附加标签。"""

    fetcher: MinQmtDataFetcher = field(default_factory=MinQmtDataFetcher)
    tag_engine: TagEngine = field(default_factory=TagEngine)
    hierarchy: PoolHierarchy = field(default_factory=PoolHierarchy)

    def list_pool_sources(self) -> list[dict[str, str]]:
        return [{"id": k, **v} for k, v in POOL_SOURCES.items()]

    def list_hierarchy(self) -> list[dict[str, str | int | None]]:
        return self.hierarchy.list_flat()

    def get_pool_path(self, node_id: str) -> str:
        return self.hierarchy.path_label(node_id)

    def promote_to_tradable(
        self,
        symbols: list[str],
        target_node: str = "trade_momentum",
    ) -> list[str]:
        """将候选标的调入可交易池。"""
        return self.hierarchy.promote_to_tradable(symbols, target_node)

    def build_from_node(
        self,
        node_id: str,
        *,
        bar_count: int = 21,
        max_stocks: int | None = None,
    ) -> pd.DataFrame:
        """按层级节点构建股票池，自动写入 pool_path / pool_level 字段。"""
        node = self.hierarchy.get_node(node_id)
        if not node:
            raise ValueError(f"未知池节点: {node_id}")

        codes = self._resolve_codes_for_node(node)
        if max_stocks:
            codes = codes[:max_stocks]
        if not codes:
            return pd.DataFrame()

        snapshot = self.fetcher.fetch_pool_snapshot(codes, bar_count=bar_count)
        if snapshot.empty:
            return snapshot

        path = self.hierarchy.get_path(node_id)
        snapshot["pool_node"] = node_id
        snapshot["pool_level"] = node.level
        snapshot["pool_kind"] = self.hierarchy.get_kind(node_id) or ""
        snapshot["pool_path"] = " › ".join(n.label for n in path)
        snapshot["pool_label"] = node.label

        index_code = next((n.index_code for n in reversed(path) if n.index_code), None)
        if index_code:
            weights = self._load_index_weights(index_code)
            if weights:
                snapshot["index_weight"] = snapshot["symbol"].map(weights).fillna(0)

        enriched = self._enrich_instrument(snapshot)
        return self.tag_engine.evaluate_batch(enriched)

    def _resolve_codes_for_node(self, node: PoolNode) -> list[str]:
        cached = self.hierarchy.resolve_symbols(node.id)
        if cached:
            return cached

        if node.sector and node.level >= 2:
            return self.fetcher.get_sector_stocks(node.sector)

        if node.index_code:
            return self.fetcher.get_index_constituents(
                node.index_code,
                sector_fallback=node.sector or "",
            )

        return []
    def build_from_sector(
        self,
        pool_id: str,
        *,
        bar_count: int = 21,
        max_stocks: int | None = None,
    ) -> pd.DataFrame:
        """兼容旧接口：pool_id 映射到 L2 节点。"""
        return self.build_from_node(pool_id, bar_count=bar_count, max_stocks=max_stocks)

    def build_custom(
        self,
        codes: list[str],
        pool_label: str = "自定义",
        **kwargs: Any,
    ) -> pd.DataFrame:
        snapshot = self.fetcher.fetch_pool_snapshot(codes, **kwargs)
        snapshot["pool"] = "custom"
        snapshot["pool_label"] = pool_label
        enriched = self._enrich_instrument(snapshot)
        return self.tag_engine.evaluate_batch(enriched)

    def _load_index_weights(self, index_code: str) -> dict[str, float]:
        try:
            raw = self.fetcher.get_index_constituents(index_code)
            xt = self.fetcher.client.xtdata
            symbol = f"{index_code}.SH" if index_code.startswith("000") else f"{index_code}.SZ"
            if hasattr(xt, "get_index_weight"):
                weights = xt.get_index_weight(symbol) or {}
                from minqmt.symbols import normalize_symbol

                return {normalize_symbol(k): float(v) for k, v in weights.items()}
        except Exception:
            pass
        return {}

    def _enrich_instrument(self, df: pd.DataFrame) -> pd.DataFrame:
        rows: list[dict[str, Any]] = []
        for _, row in df.iterrows():
            item = row.to_dict()
            detail = self.fetcher.get_instrument_detail(str(row["symbol"]))
            name = detail.get("InstrumentName") or detail.get("name") or item.get("name", "")
            item["name"] = name
            item["is_trading"] = detail.get("IsTrading", 1) == 1
            item["non_st"] = "ST" not in str(name).upper()
            rows.append(item)
        return pd.DataFrame(rows)
