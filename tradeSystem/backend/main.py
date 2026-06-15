from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# 确保 backend 目录在 path 中
_BACKEND = Path(__file__).resolve().parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

_WORKSPACE = _BACKEND.parents[2]
if str(_WORKSPACE) not in sys.path:
    sys.path.insert(0, str(_WORKSPACE))

from api.routes import backtest, data_quality, database, health, market_data, qlib, screener, strategy, symbols, sync  # noqa: E402
from config.settings import get_settings  # noqa: E402
from db import connection as db_conn  # noqa: E402
from db.repositories import settings_repo  # noqa: E402
from services.log_config import log_file_path, setup_logging  # noqa: E402

setup_logging()
logger = logging.getLogger(__name__)

FRONTEND_DIST = _BACKEND.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    logger.info("TradeSystem backend starting — DB %s:%s/%s",
                settings.postgres.host, settings.postgres.port, settings.postgres.database)
    logger.info("Sync log file: %s", log_file_path())
    try:
        db_conn.init_pool()
        if db_conn.is_connected():
            stored = settings_repo.load_settings()
            if stored:
                from config.settings import set_settings
                set_settings(settings.merge_db_row(stored))
            logger.info("PostgreSQL connected")
        else:
            logger.warning("PostgreSQL not available — data APIs will return 503")
    except Exception as exc:
        logger.warning("Database init skipped: %s", exc)
    yield
    db_conn.close_pool()


app = FastAPI(
    title="TradeSystem 股票数据获取系统",
    description="MiniQMT 数据同步 + PostgreSQL 存储",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(sync.router)
app.include_router(symbols.router)
app.include_router(screener.router)
app.include_router(qlib.router)
app.include_router(market_data.router)
app.include_router(database.router)
app.include_router(data_quality.router)
app.include_router(backtest.router)
app.include_router(strategy.router)


if FRONTEND_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(FRONTEND_DIST / "index.html")

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str) -> FileResponse:
        target = FRONTEND_DIST / full_path
        if target.is_file():
            return FileResponse(target)
        return FileResponse(FRONTEND_DIST / "index.html")
