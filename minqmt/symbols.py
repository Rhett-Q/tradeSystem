from __future__ import annotations

import re

_XT_SUFFIX_RE = re.compile(r"\.(SH|SZ|BJ)$", re.IGNORECASE)


def to_xt_symbol(code: str) -> str:
    """
    将裸代码转为 xtquant 合约代码。

    Examples:
        >>> to_xt_symbol("600519")
        '600519.SH'
        >>> to_xt_symbol("000001.SZ")
        '000001.SZ'
    """
    code = code.strip().upper()
    if _XT_SUFFIX_RE.search(code):
        return code

    if code.startswith(("6", "9")):
        return f"{code}.SH"
    if code.startswith(("0", "3")):
        return f"{code}.SZ"
    if code.startswith(("4", "8")):
        return f"{code}.BJ"
    raise ValueError(f"无法识别证券代码: {code}")


def normalize_symbol(code: str) -> str:
    """600519.SH -> 600519"""
    return _XT_SUFFIX_RE.sub("", code.strip().upper())


def to_xt_symbols(codes: list[str]) -> list[str]:
    return [to_xt_symbol(c) for c in codes]
