from __future__ import annotations

import json
import logging
import time
from typing import Any

import httpx

from services.llm.log_helper import LlmCallLogger, mask_api_key, summarize_messages, truncate

logger = logging.getLogger(__name__)


def _format_http_error(status: int, body: str) -> str:
    """从 OpenAI 兼容错误 JSON 中提取可读信息。"""
    try:
        data = json.loads(body)
        err = data.get("error", data)
        if isinstance(err, dict):
            msg = err.get("message") or err.get("msg")
            if msg:
                return f"LLM 请求失败 ({status}): {msg}"
        if isinstance(data.get("message"), str):
            return f"LLM 请求失败 ({status}): {data['message']}"
    except (json.JSONDecodeError, TypeError):
        pass
    return f"LLM 请求失败 ({status}): {truncate(body, 400)}"


def chat_completion(
    *,
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    timeout_sec: int = 60,
    temperature: float = 0.2,
    call_log: LlmCallLogger | None = None,
) -> str:
    """调用 OpenAI 兼容 Chat Completions API，返回 assistant 文本。"""
    url = base_url.rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "response_format": {"type": "json_object"},
    }
    msg_summary = summarize_messages(messages)
    total_chars = sum(m["chars"] for m in msg_summary)

    req_msg = (
        f"HTTP POST {url} · model={model} · timeout={timeout_sec}s · "
        f"key={mask_api_key(api_key)} · messages={msg_summary} · total_chars={total_chars}"
    )
    logger.info("[llm] 请求开始 %s", req_msg)
    if call_log:
        call_log.info(req_msg)
        for m in messages:
            role = m.get("role", "?")
            content = str(m.get("content", ""))
            if role == "system":
                call_log.debug(f"system prompt · {len(content)} chars · {truncate(content, 200)}")
            elif role == "user":
                # user 消息含因子目录，单独记录尾部用户需求
                user_tail = content.split("## 用户需求")[-1].strip() if "## 用户需求" in content else content
                call_log.info(
                    f"user message · {len(content)} chars · 用户需求: {truncate(user_tail, 300)}",
                )

    t0 = time.perf_counter()
    try:
        with httpx.Client(timeout=timeout_sec) as client:
            resp = client.post(url, headers=headers, json=payload)
            elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
            status = resp.status_code
            if not resp.is_success:
                detail = resp.text[:800]
                err_msg = f"HTTP {status} · elapsed={elapsed_ms}ms · body={truncate(detail, 500)}"
                logger.warning("[llm] 请求失败 %s", err_msg)
                if call_log:
                    call_log.error(err_msg)
                resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:800]
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
        friendly = _format_http_error(exc.response.status_code, detail)
        err_msg = f"{friendly} · elapsed={elapsed_ms}ms"
        logger.warning("[llm] 请求失败 %s", err_msg)
        if call_log:
            call_log.error(err_msg)
        raise RuntimeError(friendly) from exc
    except httpx.RequestError as exc:
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
        err_msg = f"连接失败 · elapsed={elapsed_ms}ms · {exc}"
        logger.warning("[llm] %s", err_msg)
        if call_log:
            call_log.error(err_msg)
        raise RuntimeError(f"无法连接 LLM 服务: {exc}") from exc

    elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
    usage = data.get("usage") if isinstance(data, dict) else None
    usage_str = ""
    if isinstance(usage, dict):
        usage_str = (
            f"prompt={usage.get('prompt_tokens', '?')} "
            f"completion={usage.get('completion_tokens', '?')} "
            f"total={usage.get('total_tokens', '?')}"
        )

    try:
        content = str(data["choices"][0]["message"]["content"])
        finish_reason = data.get("choices", [{}])[0].get("finish_reason", "")
    except (KeyError, IndexError, TypeError) as exc:
        raw_preview = json.dumps(data, ensure_ascii=False)[:500]
        err_msg = f"响应格式异常 · elapsed={elapsed_ms}ms · raw={raw_preview}"
        logger.warning("[llm] %s", err_msg)
        if call_log:
            call_log.error(err_msg)
        raise RuntimeError(f"LLM 响应格式异常: {raw_preview}") from exc

    ok_msg = (
        f"请求成功 · elapsed={elapsed_ms}ms · finish={finish_reason} · "
        f"usage=({usage_str}) · content_len={len(content)} · preview={truncate(content, 400)}"
    )
    logger.info("[llm] %s", ok_msg)
    if call_log:
        call_log.info(ok_msg)

    return content
