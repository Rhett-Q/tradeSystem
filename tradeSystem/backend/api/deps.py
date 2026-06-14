from __future__ import annotations

from fastapi import HTTPException

from db import connection as db_conn
from services.sync_engine import SyncEngine, get_sync_engine


def require_db() -> None:
    if not db_conn.is_connected():
        raise HTTPException(
            503,
            "PostgreSQL 未连接。请检查配置并执行 schema 初始化。",
        )


def get_engine() -> SyncEngine:
    return get_sync_engine()
