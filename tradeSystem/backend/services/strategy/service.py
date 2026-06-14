from __future__ import annotations

from typing import Any

from services.strategy.meta import CATEGORY_HELP, CATEGORY_LABELS
from services.strategy.registry import get_strategy_detail, list_strategies, validate_params


def get_catalog(*, category: str = "") -> dict[str, Any]:
    strategies = list_strategies(category=category)
    categories = sorted({s["category"] for s in list_strategies()})
    return {
        "total": len(strategies),
        "categories": [
            {
                "id": c,
                "label": CATEGORY_LABELS.get(c, c),
                "help": CATEGORY_HELP.get(c, ""),
                "count": sum(1 for s in list_strategies() if s["category"] == c),
            }
            for c in categories
        ],
        "category_help": CATEGORY_HELP,
        "strategies": strategies,
    }


def get_strategy(strategy_id: str) -> dict[str, Any]:
    return get_strategy_detail(strategy_id)


def validate_strategy_params(strategy_id: str, params: dict[str, Any] | None) -> dict[str, Any]:
    return validate_params(strategy_id, params)
