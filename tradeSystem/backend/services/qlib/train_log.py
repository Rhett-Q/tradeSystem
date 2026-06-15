from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


class TrainLogger:
    """模型训练 / 数据集构建日志，返回给前端并写入 backend logger。"""

    def __init__(self, task: str = "train") -> None:
        self.task = task
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
        logger.info("[qlib:%s] %s", self.task, message)

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
        logger.warning("[qlib:%s] %s", self.task, message)

    def error(self, message: str, **extra: Any) -> None:
        now = time.perf_counter()
        entry = {
            "level": "error",
            "message": message,
            "elapsed_ms": self._elapsed_ms(self._started),
            "step_ms": self._elapsed_ms(),
            **extra,
        }
        self.entries.append(entry)
        self._last = now
        logger.error("[qlib:%s] %s", self.task, message)

    def set_stat(self, key: str, value: Any) -> None:
        self.stats[key] = value

    def finish(self, message: str) -> None:
        self.stats["total_ms"] = self._elapsed_ms(self._started)
        self.info(message, step_ms=0)

    def attach(self, result: dict[str, Any]) -> dict[str, Any]:
        result["log"] = self.entries
        result["stats"] = {**self.stats, **result.get("stats", {})}
        return result

    def failure_payload(self, message: str) -> dict[str, Any]:
        self.error(message)
        self.stats["total_ms"] = self._elapsed_ms(self._started)
        return {"message": message, "log": self.entries, "stats": self.stats}


class TrainingFailedError(Exception):
    """训练失败，携带可返回前端的日志 payload。"""

    def __init__(self, message: str, log: TrainLogger) -> None:
        super().__init__(message)
        self.payload = log.failure_payload(message)
