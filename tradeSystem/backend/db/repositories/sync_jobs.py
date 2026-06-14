from __future__ import annotations

from datetime import datetime
from typing import Any

from db.connection import get_cursor


def create_job(
    job_type: str,
    period: str,
    start_date: str | None,
    batch_size: int,
) -> str:
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO sync_jobs
                (job_type, period, status, start_date, batch_size, message, created_at)
            VALUES (%s::sync_job_type, %s, 'pending'::sync_job_status, %s, %s, '等待执行', NOW())
            RETURNING id::text
            """,
            (job_type, period, start_date, batch_size),
        )
        return str(cur.fetchone()["id"])


def update_job_running(job_id: str, symbols_total: int) -> None:
    with get_cursor() as cur:
        cur.execute(
            """
            UPDATE sync_jobs SET
                status = 'running'::sync_job_status,
                symbols_total = %s,
                started_at = NOW(),
                message = '同步进行中'
            WHERE id = %s::uuid
            """,
            (symbols_total, job_id),
        )


def update_job_progress(
    job_id: str,
    symbols_done: int,
    progress: int,
    message: str = "",
) -> None:
    with get_cursor() as cur:
        cur.execute(
            """
            UPDATE sync_jobs SET
                symbols_done = %s,
                progress = %s,
                message = COALESCE(NULLIF(%s, ''), message)
            WHERE id = %s::uuid
            """,
            (symbols_done, min(progress, 100), message, job_id),
        )


def finish_job(
    job_id: str,
    status: str,
    message: str,
    symbols_done: int | None = None,
) -> None:
    with get_cursor() as cur:
        cur.execute(
            """
            UPDATE sync_jobs SET
                status = %s::sync_job_status,
                progress = CASE WHEN %s = 'completed' THEN 100 ELSE progress END,
                symbols_done = COALESCE(%s, symbols_done),
                message = %s,
                finished_at = NOW()
            WHERE id = %s::uuid
            """,
            (status, status, symbols_done, message, job_id),
        )


def get_job_status(job_id: str) -> str | None:
    with get_cursor() as cur:
        cur.execute(
            "SELECT status::text FROM sync_jobs WHERE id = %s::uuid",
            (job_id,),
        )
        row = cur.fetchone()
        return row["status"] if row else None


def cancel_job(job_id: str) -> bool:
    with get_cursor() as cur:
        cur.execute(
            """
            UPDATE sync_jobs SET
                status = 'cancelled'::sync_job_status,
                message = '用户取消',
                finished_at = NOW()
            WHERE id = %s::uuid AND status = 'running'::sync_job_status
            RETURNING id
            """,
            (job_id,),
        )
        return cur.fetchone() is not None


def list_jobs(limit: int = 50) -> list[dict[str, Any]]:
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT
                id::text,
                job_type::text AS type,
                period,
                status::text AS status,
                progress,
                symbols_total,
                symbols_done,
                start_date,
                batch_size,
                message,
                started_at,
                finished_at,
                created_at
            FROM sync_jobs
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (limit,),
        )
        return [_job_to_api(dict(r)) for r in cur.fetchall()]


def get_job(job_id: str) -> dict[str, Any] | None:
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT
                id::text,
                job_type::text AS type,
                period,
                status::text AS status,
                progress,
                symbols_total,
                symbols_done,
                start_date,
                batch_size,
                message,
                started_at,
                finished_at,
                created_at
            FROM sync_jobs WHERE id = %s::uuid
            """,
            (job_id,),
        )
        row = cur.fetchone()
        return _job_to_api(dict(row)) if row else None


def get_last_finished_at() -> datetime | None:
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT MAX(finished_at) AS t FROM sync_jobs
            WHERE status = 'completed'::sync_job_status
            """,
        )
        row = cur.fetchone()
        return row["t"] if row else None


def add_log(
    job_id: str,
    level: str,
    message: str,
    symbol: str | None = None,
) -> None:
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO sync_logs (job_id, level, symbol, message)
            VALUES (%s::uuid, %s, %s, %s)
            """,
            (job_id, level, symbol, message),
        )


def list_logs(job_id: str, limit: int = 500) -> list[dict[str, Any]]:
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT level, symbol, message, created_at
            FROM sync_logs
            WHERE job_id = %s::uuid
            ORDER BY created_at ASC
            LIMIT %s
            """,
            (job_id, limit),
        )
        rows = []
        for r in cur.fetchall():
            rows.append(
                {
                    "time": r["created_at"].strftime("%Y-%m-%d %H:%M:%S"),
                    "level": r["level"],
                    "message": r["message"],
                    "symbol": r["symbol"] or "",
                },
            )
        return rows


def has_running_job() -> bool:
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT 1 FROM sync_jobs
            WHERE status = 'running'::sync_job_status
            LIMIT 1
            """,
        )
        return cur.fetchone() is not None


def _job_to_api(row: dict[str, Any]) -> dict[str, Any]:
    for key in ("started_at", "finished_at", "created_at"):
        val = row.get(key)
        if isinstance(val, datetime):
            row[key] = val.isoformat()
    return row
