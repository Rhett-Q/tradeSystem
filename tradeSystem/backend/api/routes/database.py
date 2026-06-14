from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.deps import require_db
from config.settings import AppSettings, get_settings, set_settings
from db import connection as db_conn
from db.init_db import init_schema
from db.repositories import kline as kline_repo
from db.repositories import settings_repo

router = APIRouter(prefix="/api/database", tags=["database"])


class SettingsUpdate(BaseModel):
    minqmt: Optional[dict[str, Any]] = None
    postgres: Optional[dict[str, Any]] = None
    sync: Optional[dict[str, Any]] = None
    llm: Optional[dict[str, Any]] = None


@router.get("/tables")
def list_tables(_: None = Depends(require_db)) -> list[dict[str, Any]]:
    return kline_repo.table_stats()


@router.get("/tables/{table_name}/columns")
def list_table_columns(
    table_name: str,
    _: None = Depends(require_db),
) -> list[dict[str, Any]]:
    if table_name not in kline_repo.KNOWN_TABLES:
        raise HTTPException(404, f"未知数据表: {table_name}")
    return kline_repo.list_table_columns(table_name)


@router.get("/settings")
def get_app_settings() -> dict[str, Any]:
    settings = get_settings()
    if db_conn.is_connected():
        try:
            stored = settings_repo.load_settings()
            if stored:
                settings = settings.merge_db_row(stored)
                set_settings(settings)
        except Exception:
            pass
    return settings.to_api_dict()


@router.put("/settings")
def update_settings(body: SettingsUpdate, _: None = Depends(require_db)) -> dict[str, Any]:
    current = get_settings()
    if db_conn.is_connected():
        try:
            stored = settings_repo.load_settings()
            if stored:
                current = current.merge_db_row(stored)
        except Exception:
            pass
    merged = AppSettings.from_api_dict(body.model_dump(exclude_none=True), current)
    set_settings(merged)
    settings_repo.save_settings(merged.to_storage_dict())
    return merged.to_api_dict()


@router.post("/init")
def init_database() -> dict[str, Any]:
    try:
        db_conn.init_pool()
        init_schema()
    except Exception as exc:
        raise HTTPException(503, f"Schema 初始化失败: {exc}") from exc
    return {"ok": True, "message": "数据库 Schema 已初始化"}
