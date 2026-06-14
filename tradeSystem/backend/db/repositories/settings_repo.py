from __future__ import annotations

import json
from typing import Any

from db.connection import get_cursor


def load_settings() -> dict[str, Any] | None:
    with get_cursor() as cur:
        cur.execute("SELECT value FROM app_settings WHERE key = 'app'")
        row = cur.fetchone()
        if not row:
            return None
        return dict(row["value"])


def save_settings(data: dict[str, Any]) -> None:
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO app_settings (key, value, updated_at)
            VALUES ('app', %s::jsonb, NOW())
            ON CONFLICT (key) DO UPDATE SET
                value = EXCLUDED.value,
                updated_at = NOW()
            """,
            (json.dumps(data, ensure_ascii=False),),
        )
