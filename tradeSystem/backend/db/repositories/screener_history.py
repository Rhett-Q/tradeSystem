from __future__ import annotations

import json
from typing import Any

from db.connection import get_cursor

_MAX_ROWS = 50
_MAX_ENTRIES = 100


def _row_to_dict(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "mode": row["mode"],
        "title": row["title"],
        "query": row["query"],
        "result_summary": row["result_summary"],
        "result_rows": row["result_rows"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }


def list_history(*, limit: int = 30, offset: int = 0) -> dict[str, Any]:
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    with get_cursor() as cur:
        cur.execute("SELECT COUNT(*) AS cnt FROM screener_history")
        total = int(cur.fetchone()["cnt"])
        cur.execute(
            """
            SELECT id, mode, title, query, result_summary, result_rows, created_at
            FROM screener_history
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
            """,
            (limit, offset),
        )
        rows = [_row_to_dict(r) for r in cur.fetchall()]
    return {"total": total, "limit": limit, "offset": offset, "rows": rows}


def get_history(entry_id: str) -> dict[str, Any] | None:
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT id, mode, title, query, result_summary, result_rows, created_at
            FROM screener_history
            WHERE id = %s
            """,
            (entry_id,),
        )
        row = cur.fetchone()
    return _row_to_dict(row) if row else None


def insert_history(
    *,
    mode: str,
    title: str,
    query: dict[str, Any],
    result_summary: dict[str, Any],
    result_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    rows_snapshot = result_rows[:_MAX_ROWS]
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO screener_history (mode, title, query, result_summary, result_rows)
            VALUES (%s, %s, %s::jsonb, %s::jsonb, %s::jsonb)
            RETURNING id, mode, title, query, result_summary, result_rows, created_at
            """,
            (
                mode,
                title[:256],
                json.dumps(query, ensure_ascii=False),
                json.dumps(result_summary, ensure_ascii=False),
                json.dumps(rows_snapshot, ensure_ascii=False),
            ),
        )
        created = _row_to_dict(cur.fetchone())
        cur.execute(
            """
            DELETE FROM screener_history
            WHERE id NOT IN (
                SELECT id FROM screener_history
                ORDER BY created_at DESC
                LIMIT %s
            )
            """,
            (_MAX_ENTRIES,),
        )
    return created


def delete_history(entry_id: str) -> bool:
    with get_cursor() as cur:
        cur.execute("DELETE FROM screener_history WHERE id = %s RETURNING id", (entry_id,))
        return cur.fetchone() is not None


def clear_history() -> int:
    with get_cursor() as cur:
        cur.execute("DELETE FROM screener_history")
        return cur.rowcount
