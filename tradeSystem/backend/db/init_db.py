from __future__ import annotations

import logging
from pathlib import Path

from db.connection import get_connection, init_pool

logger = logging.getLogger(__name__)

_SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def init_schema() -> None:
    """执行 schema.sql 初始化数据库（幂等）。"""
    init_pool()
    sql = _SCHEMA_PATH.read_text(encoding="utf-8")
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
    logger.info("Database schema initialized")
