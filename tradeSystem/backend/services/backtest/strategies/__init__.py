"""兼容层：回测模块从 strategy 包读取策略。"""

from services.strategy.registry import get_strategy_class, list_strategies, validate_params

__all__ = ["get_strategy_class", "list_strategies", "validate_params"]
