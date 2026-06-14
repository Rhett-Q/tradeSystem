from __future__ import annotations

import concurrent.futures
from typing import Any

from config.settings import get_settings
from db import connection as db_conn
from db.repositories import kline as kline_repo
from db.repositories import sync_jobs as job_repo
from db.repositories import symbols as symbol_repo
from services.sync_engine import get_sync_engine

_MINQMT_CHECK_TIMEOUT = 3.0


def _probe_minqmt() -> tuple[bool, str]:
    try:
        ok = get_sync_engine().is_minqmt_connected()
        return ok, ""
    except Exception as exc:
        return False, str(exc)


def get_health() -> dict[str, Any]:
    settings = get_settings()
    pg_ok = db_conn.is_connected()
    minqmt_ok = False
    minqmt_error = ""
    universe_count = 0
    kline_rows = 0
    last_sync_at = None

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        fut = pool.submit(_probe_minqmt)
        try:
            minqmt_ok, minqmt_error = fut.result(timeout=_MINQMT_CHECK_TIMEOUT)
        except concurrent.futures.TimeoutError:
            minqmt_error = "检测超时（MiniQMT 未响应，请确认客户端已登录）"

    if pg_ok:
        try:
            universe_count = symbol_repo.count_symbols()
            kline_rows = kline_repo.count_kline_rows()
            last = job_repo.get_last_finished_at()
            if last:
                last_sync_at = last.isoformat()
        except Exception:
            pass

    pg = settings.postgres
    return {
        "minqmt_connected": minqmt_ok,
        "minqmt_account": "已连接" if minqmt_ok else (minqmt_error or "未连接"),
        "postgres_connected": pg_ok,
        "postgres_host": f"{pg.host}:{pg.port}/{pg.database}",
        "last_sync_at": last_sync_at,
        "universe_count": universe_count,
        "kline_rows": kline_rows,
    }
