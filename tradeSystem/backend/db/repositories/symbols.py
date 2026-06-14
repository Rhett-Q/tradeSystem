from __future__ import annotations

from typing import Any

from db.connection import get_cursor
from services.pinyin_utils import name_to_pinyin_fields


def _market_from_symbol(symbol: str) -> str:
    if symbol.endswith(".SH"):
        return "SH"
    if symbol.endswith(".SZ"):
        return "SZ"
    if symbol.endswith(".BJ"):
        return "BJ"
    return "SH"


def _pinyin_for_name(name: str, symbol: str) -> tuple[str, str]:
    bare = symbol.split(".", 1)[0]
    if not name or name in {symbol, bare}:
        return "", ""
    return name_to_pinyin_fields(name)


def _keyword_condition(keyword: str) -> tuple[str, list[Any]]:
    kw = f"%{keyword.strip()}%"
    kw_lower = keyword.strip().lower()
    clause = """
        (symbol ILIKE %s OR name ILIKE %s
         OR name_pinyin ILIKE %s OR name_initials ILIKE %s)
    """
    params = [kw, kw, f"%{kw_lower}%", f"%{kw_lower}%"]
    return clause, params


def upsert_symbol(
    symbol: str,
    name: str = "",
    sector: str | None = None,
    is_listed: bool = True,
) -> None:
    market = _market_from_symbol(symbol)
    display_name = name or symbol
    py_full, py_init = _pinyin_for_name(display_name, symbol)
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO symbols
                (symbol, name, market, sector, name_pinyin, name_initials, is_listed, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (symbol) DO UPDATE SET
                name = CASE WHEN EXCLUDED.name <> '' THEN EXCLUDED.name ELSE symbols.name END,
                sector = CASE
                    WHEN EXCLUDED.sector IS NOT NULL AND EXCLUDED.sector <> ''
                    THEN EXCLUDED.sector
                    ELSE symbols.sector
                END,
                name_pinyin = CASE
                    WHEN EXCLUDED.name_pinyin <> '' THEN EXCLUDED.name_pinyin
                    ELSE symbols.name_pinyin
                END,
                name_initials = CASE
                    WHEN EXCLUDED.name_initials <> '' THEN EXCLUDED.name_initials
                    ELSE symbols.name_initials
                END,
                is_listed = EXCLUDED.is_listed,
                updated_at = NOW()
            """,
            (symbol, display_name, market, sector, py_full, py_init, is_listed),
        )


def upsert_symbols_batch(rows: list[tuple[str, str, str | None, bool]]) -> int:
    if not rows:
        return 0
    with get_cursor() as cur:
        for symbol, name, sector, is_listed in rows:
            market = _market_from_symbol(symbol)
            display_name = name or symbol
            py_full, py_init = _pinyin_for_name(display_name, symbol)
            cur.execute(
                """
                INSERT INTO symbols
                    (symbol, name, market, sector, name_pinyin, name_initials, is_listed, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (symbol) DO UPDATE SET
                    name = CASE WHEN EXCLUDED.name <> '' THEN EXCLUDED.name ELSE symbols.name END,
                    sector = CASE
                        WHEN EXCLUDED.sector IS NOT NULL AND EXCLUDED.sector <> ''
                        THEN EXCLUDED.sector
                        ELSE symbols.sector
                    END,
                    name_pinyin = CASE
                        WHEN EXCLUDED.name_pinyin <> '' THEN EXCLUDED.name_pinyin
                        ELSE symbols.name_pinyin
                    END,
                    name_initials = CASE
                        WHEN EXCLUDED.name_initials <> '' THEN EXCLUDED.name_initials
                        ELSE symbols.name_initials
                    END,
                    is_listed = EXCLUDED.is_listed,
                    updated_at = NOW()
                """,
                (symbol, display_name, market, sector, py_full, py_init, is_listed),
            )
    return len(rows)


def count_symbols() -> int:
    with get_cursor() as cur:
        cur.execute("SELECT COUNT(*) AS cnt FROM symbols")
        row = cur.fetchone()
        return int(row["cnt"]) if row else 0


def mark_unlisted_except(active_symbols: list[str]) -> int:
    """将不在当前全市场列表中的标的标记为退市。"""
    if not active_symbols:
        return 0
    with get_cursor() as cur:
        cur.execute(
            """
            UPDATE symbols
            SET is_listed = FALSE, updated_at = NOW()
            WHERE is_listed = TRUE
              AND NOT (symbol = ANY(%s))
            """,
            (active_symbols,),
        )
        return cur.rowcount


def get_symbol(symbol: str) -> dict[str, Any] | None:
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT symbol, name, market, sector, is_listed AS listed
            FROM symbols
            WHERE symbol = %s
            """,
            (symbol,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def search_symbols(keyword: str, limit: int = 10) -> list[dict[str, Any]]:
    q = keyword.strip()
    if not q:
        return []

    kw = f"%{q}%"
    kw_lower = q.lower()
    kw_prefix = f"{q}%"
    kw_lower_prefix = f"{kw_lower}%"

    with get_cursor() as cur:
        cur.execute(
            """
            SELECT symbol, name, market, sector, is_listed AS listed
            FROM symbols
            WHERE symbol ILIKE %s
               OR name ILIKE %s
               OR name_pinyin ILIKE %s
               OR name_initials ILIKE %s
            ORDER BY
              CASE
                WHEN symbol ILIKE %s THEN 0
                WHEN symbol ILIKE %s THEN 1
                WHEN name ILIKE %s THEN 2
                WHEN name ILIKE %s THEN 3
                WHEN name_pinyin ILIKE %s THEN 4
                WHEN name_initials ILIKE %s THEN 5
                ELSE 6
              END,
              symbol
            LIMIT %s
            """,
            (
                kw,
                kw,
                f"%{kw_lower}%",
                f"%{kw_lower}%",
                q,
                kw_prefix,
                q,
                kw_prefix,
                kw_lower_prefix,
                kw_lower_prefix,
                limit,
            ),
        )
        return [dict(r) for r in cur.fetchall()]


def list_symbols(
    page: int = 1,
    page_size: int = 20,
    keyword: str = "",
    market: str = "",
) -> dict[str, Any]:
    offset = (page - 1) * page_size
    conditions: list[str] = []
    params: list[Any] = []

    if keyword:
        clause, kw_params = _keyword_condition(keyword)
        conditions.append(clause)
        params.extend(kw_params)
    if market:
        conditions.append("market = %s")
        params.append(market.upper())

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    with get_cursor() as cur:
        cur.execute(f"SELECT COUNT(*) AS cnt FROM symbols {where}", params)
        total = int(cur.fetchone()["cnt"])

        cur.execute(
            f"""
            SELECT symbol, name, market, sector, is_listed AS listed
            FROM symbols
            {where}
            ORDER BY symbol
            LIMIT %s OFFSET %s
            """,
            [*params, page_size, offset],
        )
        rows = [dict(r) for r in cur.fetchall()]

    return {"total": total, "page": page, "page_size": page_size, "rows": rows}
