from __future__ import annotations

import logging
from typing import Any

from db.repositories import screener_history as history_repo

logger = logging.getLogger(__name__)

_MODE_LABELS = {
    "basic": "基础筛选",
    "qlib": "Alpha158",
    "multi": "多因子",
}


def build_title(mode: str, query: dict[str, Any]) -> str:
    label = _MODE_LABELS.get(mode, mode)
    parts: list[str] = [label]

    if mode == "basic":
        if query.get("market"):
            parts.append(str(query["market"]))
        if query.get("sector"):
            parts.append(str(query["sector"]))
        cd = query.get("change_days", 5)
        if query.get("min_change_pct") is not None:
            parts.append(f"{cd}日≥{query['min_change_pct']}%")
        elif query.get("max_change_pct") is not None:
            parts.append(f"{cd}日≤{query['max_change_pct']}%")
        if query.get("above_ma"):
            parts.append(f"≥MA{query['above_ma']}")
        if query.get("below_ma"):
            parts.append(f"≤MA{query['below_ma']}")
    elif mode == "qlib":
        factor = query.get("factor", "")
        if factor:
            parts.append(str(factor))
        if query.get("min_value") is not None:
            parts.append(f"≥{query['min_value']}")
        if query.get("max_value") is not None:
            parts.append(f"≤{query['max_value']}")
    elif mode == "multi":
        conditions = query.get("conditions") or []
        if conditions:
            names = [str(c.get("factor", "")) for c in conditions if c.get("factor")]
            if names:
                parts.append(" ∩ ".join(names[:4]))
                if len(names) > 4:
                    parts.append(f"+{len(names) - 4}")

    return " · ".join(parts)


def _summary_from_result(mode: str, result: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {"total": result.get("total", 0)}
    if mode == "basic":
        summary["change_days"] = result.get("change_days")
        summary["above_ma"] = result.get("above_ma")
        summary["below_ma"] = result.get("below_ma")
    elif mode == "qlib":
        summary["factor"] = result.get("factor")
    elif mode == "multi":
        summary["factors"] = result.get("factors") or []
    if result.get("stats", {}).get("total_ms") is not None:
        summary["total_ms"] = result["stats"]["total_ms"]
    return summary


def save_screen_history(
    *,
    mode: str,
    query: dict[str, Any],
    result: dict[str, Any],
    page: int = 1,
) -> dict[str, Any] | None:
    """仅第一页选股成功后写入历史，翻页不重复记录。"""
    if page != 1:
        return None
    try:
        title = build_title(mode, query)
        return history_repo.insert_history(
            mode=mode,
            title=title,
            query=query,
            result_summary=_summary_from_result(mode, result),
            result_rows=result.get("rows") or [],
        )
    except Exception as exc:
        logger.warning("保存选股历史失败: %s", exc)
        return None
