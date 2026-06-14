from __future__ import annotations

from typing import Any

"""选股标的池公共过滤条件。"""

EXCLUDE_DELISTED_LABEL = "排除退市/非交易标的（仅正常上市）"


def symbol_is_listed(name: str, detail: dict[str, Any] | None = None) -> bool:
    """根据名称与 MiniQMT 合约详情判断是否仍在正常上市交易。

    注意：MiniQMT 的 IsTrading 在非交易时段对多数 A 股也为 False，不可用于退市判断。
    退市/整理期标的通常 ExpireDate 为具体日期，正常上市 A 股为 99999999。
    """
    label = (name or "").strip()
    if label.startswith("退市"):
        return False
    if not detail:
        return True
    expire = detail.get("ExpireDate")
    if expire is not None and str(expire) not in ("99999999", "0", ""):
        return False
    return True


def listed_symbol_where(alias: str = "") -> str:
    """SQL 片段：仅包含上市且未退市、非退市整理简称的标的。"""
    prefix = f"{alias}." if alias else ""
    return (
        f"({prefix}is_listed = TRUE "
        f"AND ({prefix}delist_date IS NULL OR {prefix}delist_date > CURRENT_DATE) "
        f"AND NOT ({prefix}name LIKE '退市%%'))"
    )
