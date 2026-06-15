from __future__ import annotations

import json
import logging
import re
from typing import Any

from config.settings import LlmSettings
from services.llm.client import chat_completion
from services.llm.log_helper import LlmCallLogger, mask_api_key
from services.qlib.catalog import get_factor_expression, list_factor_catalog
from services.qlib.factor_meta import CATEGORY_HELP, _FAMILY_META, _USAGE_EXAMPLES

logger = logging.getLogger(__name__)

_VALID_FACTORS: set[str] | None = None


def _factor_names() -> set[str]:
    global _VALID_FACTORS
    if _VALID_FACTORS is None:
        from services.qlib.catalog import list_factor_names

        _VALID_FACTORS = set(list_factor_names())
    return _VALID_FACTORS


def _build_catalog_prompt() -> str:
    families = []
    for key, meta in _FAMILY_META.items():
        families.append(
            f"- {key}: {meta.get('description', '')} "
            f"用法: {meta.get('usage', '')} "
            f"提示: {meta.get('value_hint', '')}",
        )
    examples = "\n".join(
        f"- {ex['label']}: factor={ex['factor']}, min_value={ex.get('min_value', '')}, "
        f"max_value={ex.get('max_value', '')}"
        for ex in _USAGE_EXAMPLES
    )
    categories = "\n".join(f"- {k}: {v}" for k, v in CATEGORY_HELP.items())
    names = ", ".join(sorted(_factor_names()))
    return (
        "## 因子分类\n"
        f"{categories}\n\n"
        "## 因子族说明\n"
        + "\n".join(families)
        + "\n\n## 常用示例\n"
        f"{examples}\n\n"
        "## 全部合法因子名\n"
        f"{names}\n\n"
        "## 阈值说明\n"
        "- ROC: 值越小表示涨幅越大。ROC20=0.95 约等于 20 日涨幅 ≥5%。\n"
        "- MA: ≥1.0 表示收盘在均线上方。\n"
        "- STD: 越小波动越低。\n"
        "- CORR: 量价相关系数，正相关通常 0.3~1。\n"
        "- RSV: 0~1，越大越接近区间高位。\n"
        "- VMA: >1 缩量，<1 放量。\n"
        "每个条件必须设置 min_value 或 max_value 至少一项。"
    )


def _normalize_condition(raw: dict[str, Any]) -> dict[str, Any] | None:
    factor = str(raw.get("factor", "")).strip()
    if not factor or factor not in _factor_names():
        return None
    min_value = raw.get("min_value")
    max_value = raw.get("max_value")
    if min_value is not None and min_value != "":
        min_value = float(min_value)
    else:
        min_value = None
    if max_value is not None and max_value != "":
        max_value = float(max_value)
    else:
        max_value = None
    if min_value is None and max_value is None:
        return None
    return {"factor": factor, "min_value": min_value, "max_value": max_value}


def _validate_conditions(
    conditions: list[dict[str, Any]],
    *,
    call_log: LlmCallLogger | None = None,
) -> list[dict[str, Any]]:
    if not conditions:
        raise ValueError("未能解析出有效因子条件")
    if len(conditions) > 10:
        raise ValueError("条件过多，最多 10 个因子")
    seen: set[str] = set()
    parsed: list[dict[str, Any]] = []
    dropped = 0
    for item in conditions:
        norm = _normalize_condition(item)
        if not norm:
            dropped += 1
            if call_log:
                call_log.debug(f"丢弃无效条件: {item}")
            continue
        if norm["factor"] in seen:
            dropped += 1
            if call_log:
                call_log.debug(f"丢弃重复因子: {norm['factor']}")
            continue
        if not get_factor_expression(norm["factor"]):
            dropped += 1
            if call_log:
                call_log.debug(f"丢弃未知因子: {norm['factor']}")
            continue
        seen.add(norm["factor"])
        parsed.append(norm)
    if call_log and dropped:
        call_log.warn(f"校验过滤 {dropped} 条无效/重复条件，保留 {len(parsed)} 条")
    if not parsed:
        raise ValueError("未能解析出有效因子条件，请检查描述或 LLM 配置")
    return parsed


def _parse_llm_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM 返回非 JSON: {text[:200]}") from exc
    if not isinstance(data, dict):
        raise ValueError("LLM 返回格式错误")
    return data


def _parse_with_llm(text: str, llm: LlmSettings, call_log: LlmCallLogger) -> dict[str, Any]:
    if not llm.enabled:
        raise RuntimeError("LLM 未启用")
    if not llm.api_key:
        raise RuntimeError("未配置 LLM API Key")

    call_log.info(
        f"LLM 配置 · enabled={llm.enabled} · model={llm.model} · "
        f"base_url={llm.base_url} · key={mask_api_key(llm.api_key)} · timeout={llm.timeout_sec}s",
    )

    system = (
        "你是 A 股量化选股助手，将用户的自然语言选股意图映射为 Alpha158 多因子 AND 条件。\n"
        "只输出 JSON，格式：\n"
        '{"interpretation":"简短中文解释","conditions":[{"factor":"ROC20","min_value":0.95}],'
        '"market":"","sector":""}\n'
        "规则：\n"
        "- factor 必须是合法因子名\n"
        "- 每个 condition 至少含 min_value 或 max_value\n"
        "- 条件 2~6 个为宜，不要重复因子\n"
        "- market 仅可为 SH/SZ/BJ 或空字符串\n"
        "- sector 留空除非用户明确指定行业"
    )
    catalog = _build_catalog_prompt()
    user = f"{catalog}\n\n## 用户需求\n{text.strip()}"
    call_log.info(f"构建 prompt · catalog={len(catalog)} chars · user_total={len(user)} chars")
    call_log.info(f"用户输入 · {text.strip()}")

    content = chat_completion(
        base_url=llm.base_url,
        api_key=llm.api_key,
        model=llm.model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        timeout_sec=llm.timeout_sec,
        call_log=call_log,
    )
    call_log.debug(f"LLM 原始 JSON · {content[:600]}{'...' if len(content) > 600 else ''}")

    data = _parse_llm_json(content)
    raw_conds = data.get("conditions") or []
    call_log.info(
        f"JSON 解析成功 · interpretation={data.get('interpretation', '')!r} · "
        f"raw_conditions={len(raw_conds)} · market={data.get('market', '')!r} · sector={data.get('sector', '')!r}",
    )
    conditions = _validate_conditions(raw_conds, call_log=call_log)
    call_log.info(
        f"最终条件 · {[c['factor'] for c in conditions]} · "
        f"详情={json.dumps(conditions, ensure_ascii=False)}",
    )
    return {
        "conditions": conditions,
        "interpretation": str(data.get("interpretation") or "").strip(),
        "market": str(data.get("market") or "").strip().upper(),
        "sector": str(data.get("sector") or "").strip(),
        "source": "llm",
        "warnings": [],
    }


def _match_window(text: str, default: int = 20) -> int:
    m = re.search(r"(\d+)\s*日", text)
    if m:
        n = int(m.group(1))
        if n in (5, 10, 20, 30, 60):
            return n
    return default


def _match_pct_threshold(text: str) -> float | None:
    m = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
    if not m:
        return None
    pct = float(m.group(1))
    return round(1.0 - pct / 100.0, 4)


def _parse_with_rules(text: str, call_log: LlmCallLogger | None = None) -> dict[str, Any]:
    """无 LLM 时的关键词规则解析（覆盖常见表述）。"""
    t = text.strip()
    if not t:
        raise ValueError("请输入选股描述")
    if call_log:
        call_log.info(f"规则引擎解析 · 输入={t}")

    conditions: list[dict[str, Any]] = []
    warnings: list[str] = []
    window = _match_window(t)

    def add(factor: str, *, min_value: float | None = None, max_value: float | None = None) -> None:
        if factor in _factor_names() and not any(c["factor"] == factor for c in conditions):
            conditions.append({"factor": factor, "min_value": min_value, "max_value": max_value})

    # 涨幅 / 动量
    if re.search(r"涨幅|上涨|强势|升", t):
        pct_min = _match_pct_threshold(t)
        roc = f"ROC{window}"
        add(roc, min_value=pct_min if pct_min is not None else 0.95)

    # 均线多头排列 / 空头排列
    if re.search(r"多头排列|均线多头|多头排|MA多头", t):
        for n in (5, 10, 20):
            add(f"MA{n}", min_value=1.0)
        add("BETA20", min_value=0.0)
    elif re.search(r"空头排列|均线空头|空头排|MA空头", t):
        for n in (5, 10, 20):
            add(f"MA{n}", max_value=0.98)
        add("BETA20", max_value=0.0)

    # 均线
    ma_m = re.search(r"(\d+)\s*日(?:均|移动平均)?线|MA(\d+)", t, re.I)
    ma_n = int(ma_m.group(1) or ma_m.group(2)) if ma_m else (5 if "5日" in t or "5 日" in t else 20)
    if ma_n not in (5, 10, 20, 30, 60):
        ma_n = 20
    if re.search(r"站上|突破|均线之上|高于均线|在均线上方", t):
        add(f"MA{ma_n}", min_value=1.0)
    elif re.search(r"跌破|均线之下|低于均线", t):
        add(f"MA{ma_n}", max_value=0.98)

    # 波动
    if re.search(r"低波|波动小|盘整|震荡", t):
        add(f"STD{window if window in (5, 10, 20, 30, 60) else 20}", max_value=0.02)

    # 量价
    if re.search(r"量价齐升|量价配合|量增价涨", t):
        add(f"CORR{window if window in (5, 10, 20, 30, 60) else 20}", min_value=0.3)
        if not any(c["factor"].startswith("ROC") for c in conditions):
            add(f"ROC{window if window in (5, 10, 20, 30, 60) else 10}", min_value=0.97)

    # 区间高位
    if re.search(r"高位|新高|区间上沿", t):
        add(f"RSV{window if window in (5, 10, 20, 30, 60) else 20}", min_value=0.8)

    # 量能
    if re.search(r"放量|成交量放大|量能放大", t):
        add(f"VMA{window if window in (5, 10, 20, 30, 60) else 5}", max_value=0.8)
    if re.search(r"缩量|成交量萎缩", t):
        add(f"VMA{window if window in (5, 10, 20, 30, 60) else 5}", min_value=1.2)

    # 趋势
    if re.search(r"上升趋势|趋势向上|多头趋势", t):
        add(f"BETA{window if window in (5, 10, 20, 30, 60) else 20}", min_value=0.001)
    if re.search(r"趋势清晰|线性趋势", t):
        add(f"RSQR{window if window in (5, 10, 20, 30, 60) else 20}", min_value=0.8)

    # 预设短语
    if re.search(r"强势突破", t):
        conditions.clear()
        add("ROC20", min_value=0.95)
        add("MA5", min_value=1.0)
    if re.search(r"趋势低波", t):
        conditions.clear()
        add("MA20", min_value=1.0)
        add("STD20", max_value=0.02)

    if not conditions:
        raise ValueError(
            "未能识别该描述对应的因子条件。"
            "可尝试更具体表述（如「20日涨幅超5%」「站上5日均线」「低波动盘整」），"
            "或在系统设置中启用 LLM 后使用智能解析。",
        )

    parsed = _validate_conditions(conditions, call_log=call_log)
    if len(parsed) < len(conditions):
        warnings.append("部分规则条件无效已忽略")

    market = ""
    if "上海" in t or "沪" in t:
        market = "SH"
    elif "深圳" in t or "深" in t:
        market = "SZ"
    elif "北京" in t or "北交所" in t:
        market = "BJ"

    if call_log:
        call_log.info(
            f"规则引擎完成 · 条件={[c['factor'] for c in parsed]} · market={market or '(全部)'}",
        )

    return {
        "conditions": parsed,
        "interpretation": f"规则解析：{len(parsed)} 个因子条件（{', '.join(c['factor'] for c in parsed)}）",
        "market": market,
        "sector": "",
        "source": "rules",
        "warnings": warnings,
    }


def parse_nl_to_conditions(
    text: str,
    llm: LlmSettings,
    *,
    prefer: str = "auto",
) -> dict[str, Any]:
    """将自然语言转为多因子条件。prefer: auto | llm | rules。"""
    prefer = (prefer or "auto").lower()
    call_log = LlmCallLogger(tag="nl-parse")
    call_log.info(f"开始解析 · prefer={prefer} · llm_enabled={llm.enabled} · text_len={len(text.strip())}")

    try:
        if prefer == "rules":
            result = _parse_with_rules(text, call_log)
            return call_log.attach(result)

        if prefer == "llm" or (prefer == "auto" and llm.enabled and llm.api_key):
            try:
                result = _parse_with_llm(text, llm, call_log)
                call_log.info(f"解析完成 · source=llm · conditions={len(result['conditions'])}")
                return call_log.attach(result)
            except Exception as exc:
                call_log.warn(f"LLM 解析失败: {exc}")
                logger.warning("LLM 解析失败，回退规则: %s", exc, exc_info=True)
                if prefer == "llm":
                    raise
                result = _parse_with_rules(text, call_log)
                result["warnings"] = [f"LLM 解析失败（{exc}），已使用规则引擎"]
                call_log.info(f"解析完成 · source=rules(fallback) · conditions={len(result['conditions'])}")
                return call_log.attach(result)

        call_log.info("LLM 未启用或未配置 Key，使用规则引擎")
        result = _parse_with_rules(text, call_log)
        return call_log.attach(result)
    except ValueError as exc:
        call_log.warn(f"解析失败: {exc}")
        raise
    except Exception as exc:
        call_log.error(f"解析异常终止: {exc}")
        raise
