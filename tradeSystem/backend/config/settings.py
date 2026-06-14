from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
_ENV_FILE = _BACKEND_ROOT / ".env"
load_dotenv(_ENV_FILE)


@dataclass
class PostgresSettings:
    host: str = "127.0.0.1"
    port: int = 5432
    database: str = "trade_db"
    user: str = "trade_user"
    password: str = "trade_password"

    @classmethod
    def from_env(cls) -> PostgresSettings:
        return cls(
            host=os.getenv("PG_HOST", "127.0.0.1"),
            port=int(os.getenv("PG_PORT", "5432")),
            database=os.getenv("PG_DATABASE", "trade_db"),
            user=os.getenv("PG_USER", "trade_user"),
            password=os.getenv("PG_PASSWORD", "trade_password"),
        )

    @property
    def dsn(self) -> str:
        url = os.getenv("DATABASE_URL")
        if url:
            return url
        return (
            f"postgresql://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.database}"
        )


@dataclass
class LlmSettings:
    enabled: bool = False
    base_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    model: str = "gpt-4o-mini"
    timeout_sec: int = 60

    @classmethod
    def from_env(cls) -> LlmSettings:
        return cls(
            enabled=os.getenv("LLM_ENABLED", "").lower() in ("1", "true", "yes"),
            base_url=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"),
            api_key=os.getenv("LLM_API_KEY", ""),
            model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
            timeout_sec=int(os.getenv("LLM_TIMEOUT_SEC", "60")),
        )

    def to_api_dict(self, *, mask_key: bool = True) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "base_url": self.base_url,
            "model": self.model,
            "timeout_sec": self.timeout_sec,
            "api_key": "" if mask_key else self.api_key,
            "api_key_configured": bool(self.api_key),
        }

    @classmethod
    def from_api_dict(cls, data: dict[str, Any], base: LlmSettings | None = None) -> LlmSettings:
        base = base or LlmSettings.from_env()
        incoming_key = str(data.get("api_key", "")).strip()
        if incoming_key and not incoming_key.startswith("****"):
            api_key = incoming_key
        else:
            api_key = base.api_key
        return cls(
            enabled=bool(data.get("enabled", base.enabled)),
            base_url=str(data.get("base_url", base.base_url)),
            api_key=api_key,
            model=str(data.get("model", base.model)),
            timeout_sec=int(data.get("timeout_sec", base.timeout_sec)),
        )


@dataclass
class AppSettings:
    postgres: PostgresSettings = field(default_factory=PostgresSettings.from_env)
    minqmt_path: str = field(default_factory=lambda: os.getenv("MINQMT_PATH", r"D:\gjqmt"))
    sync_default_period: str = "1d"
    sync_batch_size: int = 200
    sync_start_date: str = "20200101"
    sync_schedule_cron: str = "0 18 * * 1-5"
    llm: LlmSettings = field(default_factory=LlmSettings.from_env)

    def to_api_dict(self) -> dict[str, Any]:
        return {
            "minqmt": {
                "path": self.minqmt_path,
                "account": os.getenv("MINQMT_ACCOUNT", ""),
                "auto_connect": True,
            },
            "postgres": {
                "host": self.postgres.host,
                "port": self.postgres.port,
                "database": self.postgres.database,
                "user": self.postgres.user,
            },
            "sync": {
                "default_period": self.sync_default_period,
                "batch_size": self.sync_batch_size,
                "start_date": self.sync_start_date,
                "schedule_cron": self.sync_schedule_cron,
            },
            "llm": self.llm.to_api_dict(mask_key=True),
        }

    def to_storage_dict(self) -> dict[str, Any]:
        """写入数据库用（含 API Key，勿直接返回给前端）。"""
        data = self.to_api_dict()
        data["llm"] = self.llm.to_api_dict(mask_key=False)
        return data

    @classmethod
    def from_api_dict(cls, data: dict[str, Any], base: AppSettings | None = None) -> AppSettings:
        base = base or AppSettings()
        minqmt = data.get("minqmt") or {}
        pg = data.get("postgres") or {}
        sync = data.get("sync") or {}
        llm = data.get("llm") or {}
        return cls(
            postgres=PostgresSettings(
                host=str(pg.get("host", base.postgres.host)),
                port=int(pg.get("port", base.postgres.port)),
                database=str(pg.get("database", base.postgres.database)),
                user=str(pg.get("user", base.postgres.user)),
                password=base.postgres.password,
            ),
            minqmt_path=str(minqmt.get("path", base.minqmt_path)),
            sync_default_period=str(sync.get("default_period", base.sync_default_period)),
            sync_batch_size=int(sync.get("batch_size", base.sync_batch_size)),
            sync_start_date=str(sync.get("start_date", base.sync_start_date)),
            sync_schedule_cron=str(sync.get("schedule_cron", base.sync_schedule_cron)),
            llm=LlmSettings.from_api_dict(llm, base.llm),
        )

    def merge_db_row(self, value: dict[str, Any]) -> AppSettings:
        return AppSettings.from_api_dict(value, self)


_settings: AppSettings | None = None


def get_settings() -> AppSettings:
    global _settings
    if _settings is None:
        _settings = AppSettings()
    return _settings


def set_settings(settings: AppSettings) -> None:
    global _settings
    _settings = settings


def settings_to_json(settings: AppSettings) -> str:
    return json.dumps(settings.to_api_dict(), ensure_ascii=False)
