"""Paths into the parent tradeSystem / rdagent install."""
from __future__ import annotations

from pathlib import Path

ACADEMY_ROOT = Path(__file__).resolve().parents[2]
TRADESYSTEM_ROOT = ACADEMY_ROOT.parent
RDAGENT_ROOT = TRADESYSTEM_ROOT / "rdagent"
SCRIPTS_ROOT = TRADESYSTEM_ROOT / "scripts"
CONTENT_ROOT = ACADEMY_ROOT / "content"
LOG_ROOT = RDAGENT_ROOT / "log"
VENV_PYTHON = RDAGENT_ROOT / ".venv" / "Scripts" / "python.exe"
VENV_RDAGENT = RDAGENT_ROOT / ".venv" / "Scripts" / "rdagent.exe"
ENV_FILE = RDAGENT_ROOT / ".env"
QLIB_CN_DATA = Path.home() / ".qlib" / "qlib_data" / "cn_data"
PG_EXPORT = TRADESYSTEM_ROOT / "data" / "qlib_export"
FACTOR_H5 = (
    RDAGENT_ROOT
    / "git_ignore_folder"
    / "factor_implementation_source_data"
    / "daily_pv.h5"
)

HOST = "127.0.0.1"
PORT = 19900
FRONTEND_ORIGIN = "http://127.0.0.1:19901"