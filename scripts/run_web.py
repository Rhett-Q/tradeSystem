#!/usr/bin/env python3
"""Start MiniQMT web dashboard."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("MINQMT_WORKSPACE", str(ROOT))

from minqmt.qmt_bootstrap import configure_qmt

configure_qmt()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "web.main:app",
        host="127.0.0.1",
        port=8765,
        reload=False,
    )
