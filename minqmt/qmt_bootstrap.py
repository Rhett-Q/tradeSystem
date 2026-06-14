"""Prepare Windows DLL search paths before importing xtquant."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _qmt_root() -> Path | None:
    raw = os.environ.get("QMT_ROOT", "").strip()
    if raw and Path(raw).is_dir():
        return Path(raw)
    for candidate in (Path(r"D:\gjqmt"),):
        if candidate.is_dir():
            return candidate
    return None


def _ensure_on_syspath(path: Path, *, append: bool = True) -> None:
    s = str(path)
    if s in sys.path:
        return
    if append:
        sys.path.append(s)
    else:
        sys.path.insert(0, s)


def configure_qmt() -> Path | None:
    """
    Add QMT runtime dirs for xtquant.

    QMT site-packages is appended (not prepended) so the active Python's own
    packages (e.g. pandas) are not shadowed by QMT's bundled copies.
    """
    root = _qmt_root()
    if root is None:
        return None

    os.environ.setdefault("QMT_ROOT", str(root))

    bin_x64 = root / "bin.x64"
    site_packages = bin_x64 / "Lib" / "site-packages"
    xtquant_dir = site_packages / "xtquant"

    workspace = os.environ.get("MINQMT_WORKSPACE", "")
    if workspace and Path(workspace).is_dir():
        _ensure_on_syspath(Path(workspace), append=False)

    if site_packages.is_dir():
        _ensure_on_syspath(site_packages, append=True)

    dll_dirs: list[Path] = []
    for path in (bin_x64, xtquant_dir, Path(sys.executable).parent):
        if path.is_dir():
            dll_dirs.append(path)

    if sys.platform == "win32":
        path_parts = [str(p) for p in dll_dirs]
        os.environ["PATH"] = ";".join(path_parts + [os.environ.get("PATH", "")])
        if hasattr(os, "add_dll_directory"):
            for path in dll_dirs:
                try:
                    os.add_dll_directory(str(path))
                except OSError:
                    pass

    return root
