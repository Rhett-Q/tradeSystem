from __future__ import annotations


def name_to_pinyin_fields(name: str) -> tuple[str, str]:
    """中文名称 → (全拼, 首字母)，均为小写无分隔符。"""
    if not name:
        return "", ""

    text = name.strip()
    if not any("\u4e00" <= c <= "\u9fff" for c in text):
        return "", ""

    try:
        from pypinyin import Style, lazy_pinyin
    except ImportError:
        return "", ""

    chars = "".join(c for c in text if "\u4e00" <= c <= "\u9fff")
    if not chars:
        return "", ""

    py_list = lazy_pinyin(chars, style=Style.NORMAL)
    full = "".join(py_list).lower()
    initials = "".join(p[0] for p in py_list if p).lower()
    return full, initials
