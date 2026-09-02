"""Session / log scanning for learning console."""
from __future__ import annotations

import importlib.util
import json
import pickle
import re
import sys
from pathlib import Path

from app.config import LOG_ROOT, RDAGENT_ROOT, SCRIPTS_ROOT


def _load_session_status_module():
    path = SCRIPTS_ROOT / "rdagent_session_status.py"
    spec = importlib.util.spec_from_file_location("rdagent_session_status", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["rdagent_session_status"] = mod
    spec.loader.exec_module(mod)
    return mod


def list_sessions() -> list[dict]:
    if not LOG_ROOT.is_dir():
        return []

    mod = _load_session_status_module()
    rows: list[dict] = []
    for log_dir in sorted(LOG_ROOT.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not log_dir.is_dir():
            continue
        session = log_dir / "__session__"
        info = mod.scan_session(session) if session.is_dir() else None
        rows.append(
            {
                "id": log_dir.name,
                "log_path": f"log/{log_dir.name}",
                "mtime": log_dir.stat().st_mtime,
                "has_session": bool(info),
                "progress": info,
            }
        )
    return rows


def latest_status() -> dict:
    mod = _load_session_status_module()
    return mod.build_status()


def session_feedback(log_id: str) -> dict:
    session_root = LOG_ROOT / log_id
    if not session_root.is_dir():
        raise FileNotFoundError(log_id)

    # Prefer Loop_* directories used by summary; also support __session__ numbered dirs
    loop_dirs = sorted(
        [p for p in session_root.glob("Loop_*") if p.is_dir()],
        key=lambda p: int(re.search(r"(\d+)", p.name).group(1)) if re.search(r"(\d+)", p.name) else 0,
    )

    feedbacks = []
    for loop_dir in loop_dirs:
        pkls = list(loop_dir.glob("**/feedback/feedback/**/*.pkl"))
        if not pkls:
            continue
        try:
            with pkls[-1].open("rb") as f:
                fb = pickle.load(f)
            feedbacks.append(
                {
                    "loop": int(re.search(r"(\d+)", loop_dir.name).group(1)),
                    "decision": getattr(fb, "decision", None),
                    "observations": str(getattr(fb, "observations", ""))[:2000],
                }
            )
        except Exception as exc:
            feedbacks.append({"loop": loop_dir.name, "error": str(exc)})

    status_file = RDAGENT_ROOT / "session_status.json"
    cached = None
    if status_file.is_file():
        try:
            cached = json.loads(status_file.read_text(encoding="utf-8"))
        except Exception:
            cached = None

    return {
        "id": log_id,
        "log_path": f"log/{log_id}",
        "feedbacks": feedbacks,
        "accepted": sum(1 for f in feedbacks if f.get("decision") is True),
        "total": len(feedbacks),
        "cached_status": cached,
    }