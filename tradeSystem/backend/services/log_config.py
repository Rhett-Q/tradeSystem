from __future__ import annotations

import logging
import traceback
from pathlib import Path

_LOG_DIR = Path(__file__).resolve().parents[1] / "logs"
_LOG_FILE = _LOG_DIR / "sync.log"

_configured = False


def setup_logging() -> None:
    global _configured
    if _configured:
        return
    _LOG_DIR.mkdir(parents=True, exist_ok=True)

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    if not any(isinstance(h, logging.FileHandler) and getattr(h, "baseFilename", "") == str(_LOG_FILE) for h in root.handlers):
        fh = logging.FileHandler(_LOG_FILE, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(fmt)
        root.addHandler(fh)

    if not any(isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler) for h in root.handlers):
        sh = logging.StreamHandler()
        sh.setLevel(logging.INFO)
        sh.setFormatter(fmt)
        root.addHandler(sh)

    _configured = True


def format_error(message: str, exc: BaseException | None = None) -> str:
    if exc is None:
        return message
    tb = traceback.format_exc()
    if not tb or tb.strip() == "NoneType: None":
        tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    return f"{message}: {exc}\n{tb}"


def log_file_path() -> Path:
    return _LOG_FILE
