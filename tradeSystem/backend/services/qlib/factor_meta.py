from __future__ import annotations

import re
from typing import Any


def re_match_prefix(name: str) -> str:
    i = 0
    while i < len(name) and not name[i].isdigit():
        i += 1
    return name[:i]


# 分类说明
CATEGORY_HELP: dict[str, str] = {
    "kbar": "K 线形态因子：描述单根 K 线的实体、上下影线及偏移，常用于短线形态识别。",
    "price": "价格因子：当日或历史价格相对最新收盘价的比值（已归一化）。",
    "momentum": "动量因子：衡量价格变化速度与方向，如 ROC、涨跌天数占比。",
    "trend": "趋势因子：均线、斜率、拟合优度等，用于判断趋势强弱与线性程度。",
    "volatility": "波动因子：价格标准差，衡量振幅与风险。",
    "range": "区间因子：N 日最高/最低、分位数、RSV 等，描述价格在区间中的位置。",
    "aroon": "Aroon 类因子：距 N 日内最高/最低价出现的时间，反映趋势新鲜度。",
    "volume": "量价因子：成交量、价量相关、量能动量等。",
    "other": "其他 Alpha158 因子。",
}

# 因子族元数据（按名称前缀匹配）
_FAMILY_META: dict[str, dict[str, str]] = {
    "KMID": {
        "description": "K 线实体涨跌幅：(收盘−开盘)/开盘。",
        "usage": "min_value=0.02 筛选阳线实体超过 2%；max_value=-0.02 筛选阴线。",
        "value_hint": "正值=阳线实体；负值=阴线实体；绝对值越大实体越长。",
    },
    "KLEN": {
        "description": "K 线振幅：(最高−最低)/开盘。",
        "usage": "min_value=0.05 筛选振幅较大的活跃标的。",
        "value_hint": "越大表示当日波动越剧烈。",
    },
    "KMID2": {
        "description": "实体占振幅比例：(收盘−开盘)/(最高−最低)。",
        "usage": "接近 1 或 -1 表示几乎无影线；接近 0 表示十字星。",
        "value_hint": "范围约 [-1, 1]。",
    },
    "KUP": {
        "description": "上影线相对开盘的比例。",
        "usage": "min_value=0.03 筛选上影线较长的 K 线（上方抛压）。",
        "value_hint": "越大上影线越长。",
    },
    "KUP2": {
        "description": "上影线占整根 K 线振幅的比例。",
        "usage": "结合 KUP 判断上影强度。",
        "value_hint": "0~1 之间。",
    },
    "KLOW": {
        "description": "下影线相对开盘的比例。",
        "usage": "min_value=0.03 筛选下影线较长的 K 线（下方支撑）。",
        "value_hint": "越大下影线越长。",
    },
    "KLOW2": {
        "description": "下影线占整根 K 线振幅的比例。",
        "usage": "结合 KLOW 判断下影强度。",
        "value_hint": "0~1 之间。",
    },
    "KSFT": {
        "description": "K 线重心偏移：(2×收盘−最高−最低)/开盘。",
        "usage": "正值偏多、负值偏空，衡量收盘在振幅中的位置。",
        "value_hint": "类似威廉指标思想。",
    },
    "KSFT2": {
        "description": "K 线重心偏移（相对振幅归一化）。",
        "usage": "同 KSFT，已除以振幅。",
        "value_hint": "约 [-1, 1]。",
    },
    "OPEN": {
        "description": "开盘价相对最新收盘价（N=0 时为 1）。",
        "usage": "一般与其他因子组合使用。",
        "value_hint": "OPEN0≈开盘/收盘。",
    },
    "HIGH": {
        "description": "最高价相对最新收盘价。",
        "usage": "HIGH0 反映当日高点相对收盘位置。",
        "value_hint": "通常 ≥ 1。",
    },
    "LOW": {
        "description": "最低价相对最新收盘价。",
        "usage": "LOW0 反映当日低点相对收盘位置。",
        "value_hint": "通常 ≤ 1。",
    },
    "VWAP": {
        "description": "成交均价相对最新收盘价。",
        "usage": "VWAP0>1 表示收盘低于均价（日内偏弱）。",
        "value_hint": "由 amount/volume 或 OHLC 估算。",
    },
    "ROC": {
        "description": "N 日变化率：Ref(收盘,N)/最新收盘。数值越小表示相对 N 日前涨幅越大。",
        "usage": "min_value=0.95 筛选 20 日涨幅约 ≥5%（ROC20）；max_value=1.05 筛选约跌 5%。",
        "value_hint": "1.0=与 N 日前持平；<1 上涨；>1 下跌。ROC20=0.95 约等于 +5.3%。",
    },
    "MA": {
        "description": "N 日简单均线 / 最新收盘。衡量价格相对均线位置。",
        "usage": "min_value=1.0 筛选站上 N 日均线；max_value=0.98 筛选跌破均线。",
        "value_hint": "≥1 收盘在均线上方；<1 在下方。MA5≥1 即站上 5 日线。",
    },
    "STD": {
        "description": "N 日收盘价标准差 / 最新收盘。衡量波动率（已归一化）。",
        "usage": "min_value=0.03 筛选高波动；max_value=0.01 筛选低波动盘整。",
        "value_hint": "越大波动越强。",
    },
    "BETA": {
        "description": "N 日收盘价线性回归斜率 / 收盘。近似日均涨跌幅。",
        "usage": "min_value=0.001 筛选上升趋势；max_value=-0.001 筛选下降趋势。",
        "value_hint": "正=上涨斜率；负=下跌斜率。",
    },
    "RSQR": {
        "description": "N 日收盘价线性回归 R²。衡量趋势线性程度。",
        "usage": "min_value=0.8 筛选趋势清晰；低值表示震荡。",
        "value_hint": "0~1，越接近 1 趋势越线性。",
    },
    "RESI": {
        "description": "N 日回归残差 / 收盘。当前价偏离趋势线的程度。",
        "usage": "max_value=-0.02 筛选低于趋势线（超卖）；min_value=0.02 筛选高于趋势线。",
        "value_hint": "正=高于趋势；负=低于趋势。",
    },
    "MAX": {
        "description": "N 日最高价 / 最新收盘。",
        "usage": "min_value=1.05 筛选接近 N 日新高；值越小越接近高点。",
        "value_hint": "接近 1 表示当前价接近 N 日最高。",
    },
    "MIN": {
        "description": "N 日最低价 / 最新收盘。",
        "usage": "max_value=1.05 筛选接近 N 日新低。",
        "value_hint": "接近 1 表示当前价接近 N 日最低。",
    },
    "QTLU": {
        "description": "N 日收盘价 80% 分位数 / 最新收盘。",
        "usage": "min_value=1.0 筛选处于高分位区域。",
        "value_hint": "反映价格在高区间的位置。",
    },
    "QTLD": {
        "description": "N 日收盘价 20% 分位数 / 最新收盘。",
        "usage": "max_value=1.0 筛选处于低分位区域。",
        "value_hint": "反映价格在低区间的位置。",
    },
    "RSV": {
        "description": "N 日 RSV：(收盘−N日最低)/(N日最高−N日最低)，类似 KDJ 中的 RSV。",
        "usage": "min_value=0.8 筛选强势区；max_value=0.2 筛选弱势区。",
        "value_hint": "0~1，越高越接近区间上沿。",
    },
    "IMAX": {
        "description": "距 N 日内最高价出现的天数 / N（Aroon Up 思想）。",
        "usage": "min_value 较小表示近期刚创新高（趋势较新）。",
        "value_hint": "0=今日最高；接近 1=最高价在 N 日前。",
    },
    "IMIN": {
        "description": "距 N 日内最低价出现的天数 / N（Aroon Down 思想）。",
        "usage": "min_value 较小表示近期刚创新低。",
        "value_hint": "0=今日最低；接近 1=最低价在 N 日前。",
    },
    "IMXD": {
        "description": "IMAX − IMIN：最高与最低出现时间的差。",
        "usage": "正值大表示高点早于低点（可能转弱）；负值表示低点早于高点。",
        "value_hint": "衡量高低点先后顺序。",
    },
    "CORR": {
        "description": "N 日收盘价与 log(成交量) 的相关系数。",
        "usage": "min_value=0.5 筛选量价同向；max_value=-0.5 筛选量价背离。",
        "value_hint": "-1~1，正=价涨量增倾向。",
    },
    "CORD": {
        "description": "N 日价格变化率与成交量变化率的相关系数。",
        "usage": "判断价量变动是否同步。",
        "value_hint": "-1~1。",
    },
    "CNTP": {
        "description": "N 日内上涨天数占比。",
        "usage": "min_value=0.6 筛选多数交易日收涨。",
        "value_hint": "0~1，0.6 表示 60% 交易日上涨。",
    },
    "CNTN": {
        "description": "N 日内下跌天数占比。",
        "usage": "min_value=0.6 筛选多数交易日收跌。",
        "value_hint": "0~1。",
    },
    "CNTD": {
        "description": "上涨天数占比 − 下跌天数占比。",
        "usage": "min_value=0.2 筛选明显多头占优。",
        "value_hint": "-1~1，正=涨多跌少。",
    },
    "SUMP": {
        "description": "N 日总涨幅 / N 日绝对变动之和（类似 RSI 上涨分量）。",
        "usage": "min_value=0.6 筛选上涨动能强。",
        "value_hint": "0~1，越大上涨占比越高。",
    },
    "SUMN": {
        "description": "N 日总跌幅 / N 日绝对变动之和。",
        "usage": "min_value=0.6 筛选下跌动能强。",
        "value_hint": "0~1。",
    },
    "SUMD": {
        "description": "SUMP − SUMN，涨跌动能差。",
        "usage": "min_value=0.2 筛选多头动能占优。",
        "value_hint": "-1~1。",
    },
    "VMA": {
        "description": "N 日均量 / 最新成交量。",
        "usage": "min_value=1.2 筛选缩量；max_value=0.8 筛选放量。",
        "value_hint": ">1 当前量低于均量；<1 当前量高于均量。",
    },
    "VSTD": {
        "description": "N 日成交量标准差 / 最新成交量。",
        "usage": "衡量量能波动程度。",
        "value_hint": "越大量能波动越大。",
    },
    "WVMA": {
        "description": "成交量加权价格波动率的变异系数。",
        "usage": "min_value 筛选价量波动异常。",
        "value_hint": "量价联合波动指标。",
    },
    "VSUMP": {
        "description": "N 日成交量增加量 / 绝对变化之和。",
        "usage": "min_value=0.6 筛选量能持续放大。",
        "value_hint": "0~1。",
    },
    "VSUMN": {
        "description": "N 日成交量减少量 / 绝对变化之和。",
        "usage": "min_value=0.6 筛选量能持续萎缩。",
        "value_hint": "0~1。",
    },
    "VSUMD": {
        "description": "量能增加占比 − 减少占比。",
        "usage": "min_value=0.2 筛选量能净放大。",
        "value_hint": "-1~1。",
    },
}

# 常用筛选示例
_USAGE_EXAMPLES: list[dict[str, str]] = [
    {"factor": "ROC20", "min_value": "0.95", "label": "20 日涨幅约 ≥5%"},
    {"factor": "ROC5", "min_value": "0.98", "label": "5 日涨幅约 ≥2%"},
    {"factor": "MA5", "min_value": "1.0", "label": "站上 5 日均线"},
    {"factor": "MA20", "min_value": "1.0", "label": "站上 20 日均线"},
    {"factor": "STD20", "max_value": "0.02", "label": "低波动盘整"},
    {"factor": "RSV20", "min_value": "0.8", "label": "处于 20 日区间高位"},
    {"factor": "CORR20", "min_value": "0.5", "label": "20 日量价正相关"},
    {"factor": "CNTP10", "min_value": "0.6", "label": "10 日内多数上涨"},
]


def _parse_window(name: str) -> int | None:
    m = re.search(r"(\d+)$", name)
    return int(m.group(1)) if m else None


def _family_key(name: str) -> str:
    prefix = re_match_prefix(name)
    if name in _FAMILY_META:
        return name
    return prefix


_ALPHA360_SERIES_HELP: dict[str, str] = {
    "CLOSE": "Alpha360 收盘价序列：{n} 日前收盘相对最新收盘（CLOSE0=1）。",
    "OPEN": "Alpha360 开盘价序列：{n} 日前开盘相对最新收盘。",
    "HIGH": "Alpha360 最高价序列：{n} 日前最高相对最新收盘。",
    "LOW": "Alpha360 最低价序列：{n} 日前最低相对最新收盘。",
    "VWAP": "Alpha360 VWAP 序列：{n} 日前均价相对最新收盘。",
    "VOLUME": "Alpha360 成交量序列：{n} 日前成交量相对最新成交量（VOLUME0=1）。",
}


def get_factor_info(name: str, expression: str = "", category: str = "") -> dict[str, Any]:
    """返回单个因子的解释与用法。"""
    family = _family_key(name)
    meta = _FAMILY_META.get(family) or _FAMILY_META.get(name, {})
    window = _parse_window(name)

    if family in _ALPHA360_SERIES_HELP and window is not None:
        description = _ALPHA360_SERIES_HELP[family].format(n=window)
        meta = {
            "description": description,
            "usage": "Alpha360 原始价量序列，通常用于 ML 模型输入；单因子筛选需结合业务设定阈值。",
            "value_hint": "已相对最新价/量归一化；CLOSE0、VOLUME0 恒为 1。",
        }
    else:
        description = meta.get("description", f"Alpha158 因子 {name}。")
    if window is not None and "{n}" not in description.lower():
        description = description.replace("N 日", f"{window} 日").replace("N日", f"{window}日")

    usage = meta.get("usage", "设置 min_value / max_value 筛选因子值区间。")
    value_hint = meta.get("value_hint", "请参考 Qlib 文档与表达式含义。")

    examples = [
        ex for ex in _USAGE_EXAMPLES if ex["factor"] == name
    ]
    if not examples and family in ("ROC", "MA", "STD") and window:
        if family == "ROC":
            examples = [{"factor": name, "min_value": "0.95", "label": f"{window} 日相对强势"}]
        elif family == "MA":
            examples = [{"factor": name, "min_value": "1.0", "label": f"站上 {window} 日均线"}]

    return {
        "name": name,
        "expression": expression,
        "category": category,
        "category_label": CATEGORY_HELP.get(category, category),
        "description": description,
        "usage": usage,
        "value_hint": value_hint,
        "window": window,
        "examples": examples,
    }


def enrich_factor(factor: dict[str, str], library: str = "") -> dict[str, Any]:
    info = get_factor_info(
        factor["name"],
        factor.get("expression", ""),
        factor.get("category", ""),
    )
    if library:
        info["library_id"] = library
    return {**factor, **info}


def list_usage_examples() -> list[dict[str, str]]:
    return list(_USAGE_EXAMPLES)
