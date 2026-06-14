from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


def mask_api_key(key: str) -> str:
    if not key:
        return "(未配置)"
    if len(key) <= 8:
        return "****"
    return f"{key[:4]}...{key[-4:]}"


def summarize_messages(messages: list[dict[str, str]]) -> list[dict[str, Any]]:
    return [
        {
            "role": m.get("role", "?"),
            "chars": len(str(m.get("content", ""))),
        }
        for m in messages
    ]


def truncate(text: str, limit: int = 400) -> str:
    text = text.replace("\n", "\\n")
    if len(text) <= limit:
        return text
    return text[:limit] + f"...(+{len(text) - limit} chars)"


class LlmCallLogger:
    """LLM 调用过程日志：写入 backend logger 并收集条目供 API 返回。"""

    def __init__(self, tag: str = "nl-parse") -> None:
        self.tag = tag
        self.entries: list[dict[str, Any]] = []
        self._started = time.perf_counter()
        self._last = self._started

    def _elapsed_ms(self, since: float | None = None) -> float:
        base = since if since is not None else self._last
        return round((time.perf_counter() - base) * 1000, 1)

    def _append(self, level: str, message: str, **extra: Any) -> None:
        now = time.perf_counter()
        entry = {
            "level": level,
            "message": message,
            "elapsed_ms": self._elapsed_ms(self._started),
            "step_ms": self._elapsed_ms(),
            **extra,
        }
        self.entries.append(entry)
        self._last = now
        log_fn = logger.info if level == "info" else logger.warning if level == "warn" else logger.debug
        log_fn("[llm:%s] %s", self.tag, message)

    def info(self, message: str, **extra: Any) -> None:
        self._append("info", message, **extra)

    def warn(self, message: str, **extra: Any) -> None:
        self._append("warn", message, **extra)

    def debug(self, message: str, **extra: Any) -> None:
        self._append("debug", message, **extra)

    def error(self, message: str, **extra: Any) -> None:
        self._append("warn", message, **extra)
        logger.error("[llm:%s] %s", self.tag, message)

    def attach(self, result: dict[str, Any]) -> dict[str, Any]:
        result["log"] = self.entries
        result["stats"] = {
            "total_ms": self._elapsed_ms(self._started),
            "steps": len(self.entries),
        }
        return result
