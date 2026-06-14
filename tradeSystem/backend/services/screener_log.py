from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


class ScreenLogger:
    """选股运行日志，返回给前端并写入 backend logger。"""

    def __init__(self, mode: str) -> None:
        self.mode = mode
        self.entries: list[dict[str, Any]] = []
        self.stats: dict[str, Any] = {}
        self._started = time.perf_counter()
        self._last = self._started

    def _elapsed_ms(self, since: float | None = None) -> float:
        base = since if since is not None else self._last
        return round((time.perf_counter() - base) * 1000, 1)

    def info(self, message: str, **extra: Any) -> None:
        now = time.perf_counter()
        entry = {
            "level": "info",
            "message": message,
            "elapsed_ms": self._elapsed_ms(self._started),
            "step_ms": self._elapsed_ms(),
            **extra,
        }
        self.entries.append(entry)
        self._last = now
        logger.info("[screener:%s] %s", self.mode, message)

    def warn(self, message: str, **extra: Any) -> None:
        now = time.perf_counter()
        entry = {
            "level": "warn",
            "message": message,
            "elapsed_ms": self._elapsed_ms(self._started),
            "step_ms": self._elapsed_ms(),
            **extra,
        }
        self.entries.append(entry)
        self._last = now
        logger.warning("[screener:%s] %s", self.mode, message)

    def set_stat(self, key: str, value: Any) -> None:
        self.stats[key] = value

    def finish(self, message: str) -> None:
        total_ms = self._elapsed_ms(self._started)
        self.stats["total_ms"] = total_ms
        self.info(message, step_ms=0)

    def attach(self, result: dict[str, Any]) -> dict[str, Any]:
        result["log"] = self.entries
        result["stats"] = self.stats
        return result
