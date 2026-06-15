from __future__ import annotations

from typing import Any

from services.qlib.catalog import get_factor_expression
from services.qlib.factor_meta import get_factor_info


def parse_factor_conditions(raw: list[dict[str, Any]], library: str = "") -> list[dict[str, Any]]:
    if not raw:
        raise ValueError("至少需要一个因子条件")
    if len(raw) > 10:
        raise ValueError("最多 10 个因子条件")

    parsed: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw:
        name = str(item.get("factor", "")).strip()
        if not name:
            raise ValueError("因子名不能为空")
        if name in seen:
            raise ValueError(f"因子 {name} 重复，请合并阈值")
        seen.add(name)

        expr = get_factor_expression(name, library)
        if not expr:
            raise ValueError(f"未知因子: {name}")

        min_value = item.get("min_value")
        max_value = item.get("max_value")
        if min_value is not None:
            min_value = float(min_value)
        if max_value is not None:
            max_value = float(max_value)
        if min_value is None and max_value is None:
            raise ValueError(f"因子 {name} 需设置 min_value 或 max_value")

        parsed.append(
            {
                "factor": name,
                "expression": expr,
                "min_value": min_value,
                "max_value": max_value,
                "factor_info": get_factor_info(name, expr),
            },
        )
    return parsed


def passes_threshold(
    val: float | None,
    min_value: float | None,
    max_value: float | None,
) -> bool:
    if val is None:
        return False
    if min_value is not None and val < min_value:
        return False
    if max_value is not None and val > max_value:
        return False
    return True
