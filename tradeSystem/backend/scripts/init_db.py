"""初始化 PostgreSQL Schema。"""
from __future__ import annotations

import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from db.connection import init_pool, is_connected  # noqa: E402
from db.init_db import init_schema  # noqa: E402


def main() -> None:
    init_pool()
    if not is_connected():
        print("无法连接 PostgreSQL，请检查 backend/.env 配置")
        sys.exit(1)
    init_schema()
    print("Schema 初始化完成")


if __name__ == "__main__":
    main()
