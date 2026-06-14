#!/usr/bin/env python3
"""Configure MiniQMT environment and write scripts/env.bat for CMD sessions."""

from __future__ import annotations

import glob
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
ROOT = SCRIPTS_DIR.parent
ENV_BAT = SCRIPTS_DIR / "env.bat"

SUB_PATHS = (
    Path("bin.x64") / "Lib" / "site-packages",
    Path("bin") / "Lib" / "site-packages",
    Path("Lib") / "site-packages",
)

IMPORT_TEST = """
import os, sys
from pathlib import Path
qmt = Path(os.environ['QMT_ROOT'])
bin_x64 = qmt / 'bin.x64'
xt_site = bin_x64 / 'Lib' / 'site-packages'
if str(xt_site) not in sys.path:
    sys.path.append(str(xt_site))
if hasattr(os, 'add_dll_directory'):
    os.add_dll_directory(str(bin_x64))
    os.add_dll_directory(str(xt_site / 'xtquant'))
os.environ['PATH'] = str(bin_x64) + ';' + str(xt_site / 'xtquant') + ';' + os.environ.get('PATH', '')
from xtquant import xtdata
print('OK')
"""

# Microsoft Store stubs — not real Python (WinError 1920 on resolve/run)
_WINDOWS_APPS_MARKERS = (
    "\\windowsapps\\",
    "/windowsapps/",
)


def _is_usable_python(exe: Path) -> bool:
    raw = str(exe).lower()
    if any(m in raw for m in _WINDOWS_APPS_MARKERS):
        return False
    try:
        resolved = exe.resolve(strict=False)
    except OSError:
        return False
    if not resolved.is_file():
        return False
    try:
        if resolved.stat().st_size == 0:
            return False
    except OSError:
        return False
    return True


def _resolve_python(exe: Path) -> Path | None:
    if not _is_usable_python(exe):
        return None
    try:
        return exe.resolve()
    except OSError:
        return None


def find_xtquant() -> tuple[Path, Path] | None:
    roots: list[Path] = []
    if os.environ.get("QMT_ROOT"):
        roots.append(Path(os.environ["QMT_ROOT"]))
    roots.append(Path(r"D:\gjqmt"))

    for root in roots:
        if not root.is_dir():
            continue
        for sub in SUB_PATHS:
            site = root / sub
            if (site / "xtquant").is_dir():
                return root, site
    return None


def _parse_py_launcher_list() -> list[Path]:
    exe_paths: list[Path] = []
    try:
        proc = subprocess.run(
            ["py", "-0p"],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return exe_paths

    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line or "python.exe" not in line.lower():
            continue
        match = re.search(r"([A-Za-z]:\\[^\s]+python\.exe)", line, re.I)
        if match:
            exe_paths.append(Path(match.group(1)))
    return exe_paths


def _python_version(argv: list[str]) -> tuple[int, int] | None:
    try:
        proc = subprocess.run(
            [*argv, "-c", "import sys; print(sys.version_info[0], sys.version_info[1])"],
            capture_output=True,
            timeout=15,
        )
        if proc.returncode != 0:
            return None
        out = (proc.stdout or b"").decode("utf-8", errors="replace").strip().split()
        if len(out) >= 2:
            return int(out[0]), int(out[1])
    except (subprocess.TimeoutExpired, OSError, ValueError):
        pass
    return None


def discover_python_executables(qmt_root: Path | None) -> list[tuple[str, list[str]]]:
    """Return [(label, argv), ...] unique executables to try for xtquant."""
    seen: set[str] = set()
    candidates: list[tuple[str, list[str]]] = []

    def add(exe: Path, label: str) -> None:
        resolved = _resolve_python(exe)
        if resolved is None:
            return
        if resolved.name.lower() == "pythonw.exe":
            return
        ver = _python_version([str(resolved)])
        if ver and ver < (3, 8):
            return
        key = str(resolved).lower()
        if key in seen:
            return
        seen.add(key)
        ver_label = f"Python {ver[0]}.{ver[1]}" if ver else label
        candidates.append((f"{ver_label} ({resolved})", [str(resolved)]))

    for exe in _parse_py_launcher_list():
        if not _is_usable_python(exe):
            continue
        ver = ""
        try:
            proc = subprocess.run(
                [str(exe), "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if proc.returncode == 0:
                ver = proc.stdout.strip()
        except (subprocess.TimeoutExpired, OSError):
            continue
        add(exe, f"Python {ver} ({exe})" if ver else str(exe))

    for args, label in (
        (["py", "-3.11"], "py -3.11"),
        (["py", "-3.10"], "py -3.10"),
        (["py", "-3.9"], "py -3.9"),
        (["py", "-3.8"], "py -3.8"),
        (["py", "-3.7"], "py -3.7"),
        (["py", "-3.6"], "py -3.6"),
        (["py", "-3"], "py -3"),
    ):
        exe = _resolve_via_launcher(args)
        if exe:
            add(exe, label)

    globs = [
        r"D:\Python\Python*\python.exe",
        r"C:\Python*\python.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python\Python*\python.exe"),
        os.path.expandvars(r"%ProgramFiles%\Python*\python.exe"),
    ]
    for pattern in globs:
        for match in sorted(glob.glob(pattern), reverse=True):
            add(Path(match), match)

    if qmt_root:
        add(qmt_root / "bin.x64" / "python.exe", "QMT bundled (python.exe)")

    for cmd in ("python",):
        found = shutil.which(cmd)
        if found:
            add(Path(found), cmd)

    if sys.executable and _is_usable_python(Path(sys.executable)):
        add(Path(sys.executable), f"current ({sys.executable})")

    return candidates


def _resolve_via_launcher(launcher: list[str]) -> Path | None:
    try:
        proc = subprocess.run(
            [*launcher, "-c", "import sys; print(sys.executable)"],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        return None
    exe = proc.stdout.strip()
    if exe:
        p = Path(exe)
        if _is_usable_python(p):
            return p.resolve()
    return None


def _env_for_xtquant(python_argv: list[str]) -> dict[str, str]:
    """Only workspace on PYTHONPATH; QMT xtquant path is added in-process (append)."""
    env = os.environ.copy()
    env["MINQMT_WORKSPACE"] = str(ROOT)
    env["PYTHONPATH"] = str(ROOT)
    return env


def _pip_requirements(python_argv: list[str], *, quiet: bool = True) -> None:
    req = ROOT / "requirements.txt"
    if not req.is_file():
        return
    args = [*python_argv, "-m", "pip", "install"]
    if quiet:
        args.append("-q")
    args.extend(["-r", str(req)])
    print("  Installing project dependencies (pandas, fastapi, uvicorn) ...")
    subprocess.run(args, cwd=ROOT, timeout=600)


def _ensure_project_deps(python_argv: list[str]) -> None:
    try:
        proc = subprocess.run(
            [*python_argv, "-c", "import pandas, fastapi, uvicorn"],
            capture_output=True,
            timeout=30,
        )
        if proc.returncode == 0:
            return
    except (subprocess.TimeoutExpired, OSError):
        pass
    _pip_requirements(python_argv)


def test_xtquant(argv: list[str], site_packages: Path, qmt_root: Path) -> tuple[bool, str]:
    env = _env_for_xtquant(argv)
    bin_x64 = qmt_root / "bin.x64"
    xtquant_dir = site_packages / "xtquant"
    env["QMT_ROOT"] = str(qmt_root)
    env["PATH"] = f"{bin_x64};{xtquant_dir};{env.get('PATH', '')}"

    try:
        proc = subprocess.run(
            [*argv, "-c", IMPORT_TEST],
            cwd=ROOT,
            env=env,
            capture_output=True,
            timeout=60,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return False, str(exc)

    if proc.returncode == 0:
        return True, ""
    err = (proc.stderr or proc.stdout or b"").decode("utf-8", errors="replace").strip()
    if len(err) > 400:
        err = err[:400] + "..."
    return False, err


def _bat_text(value: str) -> str:
    """Ensure env.bat content is ASCII-safe for Windows CMD."""
    return value.encode("ascii", errors="replace").decode("ascii")


def write_env_bat(
    qmt_root: Path,
    site_packages: Path,
    python_exe: str,
    py_label: str,
) -> None:
    bin_x64 = qmt_root / "bin.x64"
    xtquant_dir = site_packages / "xtquant"
    work = ROOT
    lines = [
        "@echo off",
        "rem Auto-generated by scripts/setup_env.py - do not edit",
        f'set "QMT_ROOT={_bat_text(str(qmt_root))}"',
        f'set "MINQMT_WORKSPACE={_bat_text(str(work))}"',
        f'set "MINQMT_PYTHON_EXE={_bat_text(python_exe)}"',
        f'set "MINQMT_PYTHON={_bat_text(py_label)}"',
        f'set "PYTHONPATH={_bat_text(str(work))}"',
        f'set "PATH={_bat_text(str(bin_x64))};{_bat_text(str(xtquant_dir))};%PATH%"',
    ]
    ENV_BAT.write_text("\r\n".join(lines) + "\r\n", encoding="ascii")


def main() -> int:
    found = find_xtquant()
    if not found:
        print("[ERROR] xtquant not found.")
        print('Set QMT_ROOT, e.g.: set QMT_ROOT=D:\\gjqmt')
        print("Then run: python scripts\\setup_env.py")
        return 1

    qmt_root, site_packages = found
    bin_x64 = qmt_root / "bin.x64"
    xtquant_dir = site_packages / "xtquant"

    os.environ["QMT_ROOT"] = str(qmt_root)
    os.environ["PATH"] = f"{bin_x64};{xtquant_dir};{os.environ.get('PATH', '')}"

    candidates = discover_python_executables(qmt_root)
    if not candidates:
        print("[ERROR] No real Python interpreter found on this machine.")
        print("(Ignored Windows Store stubs under ...\\WindowsApps\\)")
        print("Install 64-bit Python 3.9 from https://www.python.org/downloads/")
        print("During install, check 'Add python.exe to PATH'.")
        print("Optional: Settings > Apps > Advanced > App execution aliases")
        print("          turn OFF python.exe / python3.exe aliases")
        return 1

    print(f"Found {len(candidates)} Python installation(s). Testing xtquant...")
    print()

    chosen_label = ""
    chosen_argv: list[str] | None = None
    failures: list[str] = []

    for label, argv in candidates:
        ok, err = test_xtquant(argv, site_packages, qmt_root)
        if ok:
            chosen_label = label
            chosen_argv = argv
            print(f"  [OK] {label}")
            break
        print(f"  [FAIL] {label}")
        failures.append(f"  - {label}: {err}")

    if not chosen_argv:
        print()
        print("[ERROR] xtquant import failed for every Python on this PC.")
        print()
        for line in failures[:8]:
            print(line)
        if len(failures) > 8:
            print(f"  ... and {len(failures) - 8} more")
        print()
        print("Most likely fix:")
        print("  1. Install deps: \"<python>\" -m pip install -r requirements.txt")
        print("  2. Re-run: scripts\\setup_env.cmd")
        print()
        print("Optional: re-download xtquant in QMT client")
        print("  Settings > Model settings > Python library download")
        print()
        pyd_files = sorted((site_packages / "xtquant").glob("IPythonApiClient.cp*.pyd"))
        if pyd_files:
            print("Available xtquant wheels:", ", ".join(p.name for p in pyd_files))
        return 1

    python_exe = chosen_argv[0]
    write_env_bat(qmt_root, site_packages, python_exe, chosen_label)
    _ensure_project_deps(chosen_argv)

    print()
    print(f"[OK] QMT_ROOT          = {qmt_root}")
    print(f"[OK] PYTHONPATH        = {ROOT}  (QMT xtquant via sys.path append)")
    print(f"[OK] PATH              += {bin_x64}; {xtquant_dir}")
    print(f"[OK] MINQMT_PYTHON     = {chosen_label}")
    print(f"[OK] MINQMT_PYTHON_EXE = {python_exe}")
    print(f"[OK] WORKDIR           = {ROOT}")
    print(f"[OK] Wrote             = {ENV_BAT}")
    print()
    print("[OK] xtquant import success")
    print()
    print("Next steps:")
    print("  scripts\\run_web.cmd")
    print(f'  "{python_exe}" scripts\\sync_market.py universe')
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    raise SystemExit(main())
