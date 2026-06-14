from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.deps import get_engine, require_db
from db.repositories import sync_jobs as job_repo
from services.log_config import log_file_path
from services.sync_engine import SyncEngine

router = APIRouter(prefix="/api/sync", tags=["sync"])


class SyncStartRequest(BaseModel):
    mode: str = Field(description="full | incremental")
    period: str = "1d"
    start_date: str = "20200101"
    batch_size: int = 200


@router.get("/jobs")
def list_jobs(_: None = Depends(require_db)) -> list[dict[str, Any]]:
    return job_repo.list_jobs()


@router.get("/jobs/{job_id}")
def get_job(job_id: str, _: None = Depends(require_db)) -> dict[str, Any]:
    job = job_repo.get_job(job_id)
    if not job:
        raise HTTPException(404, "任务不存在")
    return job


@router.get("/jobs/{job_id}/logs")
def get_job_logs(
    job_id: str,
    limit: int = 500,
    _: None = Depends(require_db),
) -> list[dict[str, Any]]:
    if not job_repo.get_job(job_id):
        raise HTTPException(404, "任务不存在")
    return job_repo.list_logs(job_id, limit=limit)


@router.get("/log-file")
def get_log_file_info() -> dict[str, str]:
    """返回后端 sync 日志文件路径，便于排查。"""
    path = log_file_path()
    return {
        "path": str(path),
        "exists": str(path.is_file()),
        "hint": "完整堆栈与批次明细写入此文件及 sync_logs 表",
    }


@router.post("/jobs/{job_id}/cancel")
def cancel_job(
    job_id: str,
    engine: SyncEngine = Depends(get_engine),
    _: None = Depends(require_db),
) -> dict[str, Any]:
    if not job_repo.get_job(job_id):
        raise HTTPException(404, "任务不存在")
    ok = engine.cancel_job(job_id)
    return {"ok": ok, "message": "已取消" if ok else "任务未在运行"}


@router.post("/start")
def start_sync(
    body: SyncStartRequest,
    engine: SyncEngine = Depends(get_engine),
    _: None = Depends(require_db),
) -> dict[str, Any]:
    if body.mode not in ("full", "incremental"):
        raise HTTPException(400, "mode 必须为 full 或 incremental")
    if body.period in ("1w", "1mon"):
        label = "周线" if body.period == "1w" else "月线"
        raise HTTPException(
            400,
            f"{label}（{body.period}）由日 K 重采样，请同步日线 1d",
        )
    try:
        job_id = engine.start_job(
            mode=body.mode,
            period=body.period,
            start_date=body.start_date,
            batch_size=body.batch_size,
        )
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    except ConnectionError as exc:
        raise HTTPException(503, str(exc)) from exc
    return {
        "ok": True,
        "message": f"已提交 {body.mode} 同步任务",
        "job_id": job_id,
    }
