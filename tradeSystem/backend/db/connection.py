from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Generator, Iterator

import psycopg2
import psycopg2.pool
from psycopg2.extras import RealDictCursor

from config.settings import get_settings

logger = logging.getLogger(__name__)

_pool: psycopg2.pool.ThreadedConnectionPool | None = None


def init_pool(minconn: int = 1, maxconn: int = 10) -> None:
    global _pool
    if _pool is not None:
        return
    dsn = get_settings().postgres.dsn
    _pool = psycopg2.pool.ThreadedConnectionPool(minconn, maxconn, dsn)
    logger.info("PostgreSQL connection pool initialized")


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.closeall()
        _pool = None


def is_connected() -> bool:
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        return True
    except Exception as exc:
        logger.debug("PostgreSQL ping failed: %s", exc)
        return False


@contextmanager
def get_connection() -> Generator[Any, None, None]:
    if _pool is None:
        init_pool()
    assert _pool is not None
    conn = _pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _pool.putconn(conn)


@contextmanager
def get_cursor(dict_cursor: bool = True) -> Iterator[Any]:
    with get_connection() as conn:
        factory = RealDictCursor if dict_cursor else None
        with conn.cursor(cursor_factory=factory) as cur:
            yield cur
