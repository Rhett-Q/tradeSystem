from __future__ import annotations

import ast
import re
import uuid
from typing import Any

# 允许出现在表达式中的变量名（来自 fetch_pool_snapshot / instrument detail）
FILTER_FIELD_DOCS: dict[str, str] = {
    "close": "最新收盘价",
    "open": "最新开盘价",
    "high": "最新最高价",
    "low": "最新最低价",
    "volume": "成交量",
    "amount": "成交额 (元)",
    "momentum_20d": "20 日涨跌幅 (%)",
    "pct_change": "最新一日涨跌幅 (%)",
    "index_weight": "指数权重 (%)",
    "non_st": "非 ST (bool)",
    "is_trading": "可交易 (bool)",
    "roe": "ROE (小数，如 0.15)",
}

ALLOWED_AST_NODES = (
    ast.Expression,
    ast.BoolOp,
    ast.BinOp,
    ast.UnaryOp,
    ast.Compare,
    ast.Name,
    ast.Load,
    ast.Constant,
    ast.And,
    ast.Or,
    ast.Not,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Mod,
    ast.USub,
)


class FilterExprError(ValueError):
    pass


def _validate_ast(node: ast.AST) -> None:
    if not isinstance(node, ALLOWED_AST_NODES):
        raise FilterExprError(f"不支持的语法: {type(node).__name__}")
    for child in ast.iter_child_nodes(node):
        _validate_ast(child)


def normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    """统一字段名，供表达式求值。"""
    ctx = dict(row)
    if "pct_change" not in ctx and "pctChange" in ctx:
        ctx["pct_change"] = ctx["pctChange"]
    if "momentum_20d" not in ctx and "momentum20d" in ctx:
        ctx["momentum_20d"] = ctx["momentum20d"]
    if "non_st" not in ctx:
        name = str(ctx.get("name", ""))
        ctx["non_st"] = "ST" not in name.upper()
    if "is_trading" not in ctx:
        ctx["is_trading"] = ctx.get("IsTrading", ctx.get("is_trading", True)) == 1 or bool(
            ctx.get("is_trading", True),
        )
    for key in FILTER_FIELD_DOCS:
        if key not in ctx:
            ctx[key] = 0 if key not in ("non_st", "is_trading") else False
    return ctx


def eval_filter_expr(expr: str, row: dict[str, Any]) -> bool:
    """
    对单行快照求值过滤表达式。

    示例::
        eval_filter_expr("momentum_20d > 10 and amount > 2e8", row)
        eval_filter_expr("non_st", row)
        eval_filter_expr("close > 10 and pct_change > 0", row)
    """
    expr = expr.strip()
    if not expr:
        raise FilterExprError("表达式不能为空")

    ctx = normalize_row(row)

    if re.fullmatch(r"[a-z_][a-z0-9_]*", expr, re.I):
        val = ctx.get(expr)
        if isinstance(val, bool):
            return val
        if val is not None:
            return bool(val)

    tree = ast.parse(expr, mode="eval")
    _validate_ast(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id not in FILTER_FIELD_DOCS:
            raise FilterExprError(f"未知变量: {node.id}")

    try:
        return bool(eval(compile(tree, "<filter>", "eval"), {"__builtins__": {}}, ctx))
    except Exception as exc:
        raise FilterExprError(f"求值失败: {exc}") from exc


def validate_filter_expr(expr: str) -> tuple[bool, str]:
    """校验表达式语法，返回 (ok, message)。"""
    expr = expr.strip()
    if not expr:
        return False, "表达式不能为空"
    try:
        if re.fullmatch(r"[a-z_][a-z0-9_]*", expr, re.I):
            if expr not in FILTER_FIELD_DOCS:
                return False, f"未知字段: {expr}"
            return True, "语法正确"
        tree = ast.parse(expr, mode="eval")
        _validate_ast(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id not in FILTER_FIELD_DOCS:
                return False, f"未知变量: {node.id}"
        return True, "语法正确"
    except FilterExprError as exc:
        return False, str(exc)
    except Exception as exc:
        return False, str(exc)


def new_filter_id() -> str:
    return f"custom_{uuid.uuid4().hex[:8]}"
