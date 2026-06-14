#!/usr/bin/env python3
"""List and uninstall old Python versions on Windows (keep 3.9–3.11 for xtquant)."""

from __future__ import annotations

import argparse
import glob
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

# xtquant ships wheels up to cp311; 3.9+ recommended
DEFAULT_KEEP = frozenset(((3, 9), (3, 10), (3, 11)))

WINDOWS_APPS = "\\windowsapps\\"


@dataclass
class _ProcResult:
    returncode: int
    stdout: str
    stderr: str


@dataclass
class PythonInstall:
    version: tuple[int, int]
    label: str
    source: str  # winget | launcher | path
    uninstall_cmd: list[str] | None = None
    path: str = ""


def _decode_bytes(data: bytes | None) -> str:
    if not data:
        return ""
    for encoding in ("utf-8", "gbk", "cp936"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _run(cmd: list[str], timeout: int = 120) -> _ProcResult:
    """Run command; decode bytes manually (avoids GBK UnicodeDecodeError on Windows)."""
    proc = subprocess.run(
        cmd,
        capture_output=True,
        timeout=timeout,
        shell=False,
    )
    stdout = _decode_bytes(proc.stdout)
    stderr = _decode_bytes(proc.stderr)
    if not stdout.strip() and stderr.strip():
        stdout = stderr
    return _ProcResult(proc.returncode, stdout, stderr)


def _output(proc: _ProcResult) -> str:
    return proc.stdout or proc.stderr or ""


def _parse_version(text: str) -> tuple[int, int] | None:
    m = re.search(r"(3)\.(\d+)", text)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def _should_keep(ver: tuple[int, int], keep: frozenset[tuple[int, int]]) -> bool:
    return ver in keep


def discover_via_py_launcher() -> list[PythonInstall]:
    found: list[PythonInstall] = []
    try:
        proc = _run(["py", "-0p"], timeout=20)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return found

    for line in _output(proc).splitlines():
        line = line.strip()
        if "python.exe" not in line.lower():
            continue
        m = re.search(r"(-V:([\d.]+)\s+\*)?\s*([A-Za-z]:\\[^\s]+python\.exe)", line, re.I)
        if not m:
            continue
        exe = m.group(3)
        if WINDOWS_APPS in exe.lower():
            continue
        ver_str = m.group(2) or ""
        ver = _parse_version(ver_str) or _python_version_from_exe(exe)
        if not ver:
            continue
        found.append(
            PythonInstall(
                version=ver,
                label=f"py launcher {ver[0]}.{ver[1]}",
                source="launcher",
                path=exe,
            ),
        )
    return found


def _python_version_from_exe(exe: str) -> tuple[int, int] | None:
    try:
        proc = _run([exe, "-c", "import sys; print(sys.version_info[:2])"], timeout=15)
        if proc.returncode != 0:
            return None
        parts = _output(proc).strip().strip("()").split(",")
        if len(parts) >= 2:
            return int(parts[0].strip()), int(parts[1].strip())
    except (OSError, subprocess.TimeoutExpired, ValueError):
        pass
    return None


def discover_via_winget() -> list[PythonInstall]:
    found: list[PythonInstall] = []
    try:
        proc = _run(
            ["winget", "list", "--name", "Python", "--accept-source-agreements"],
            timeout=90,
        )
    except FileNotFoundError:
        return found
    except subprocess.TimeoutExpired:
        return found

    for line in _output(proc).splitlines():
        if "Python.Python." not in line:
            continue
        m = re.search(r"Python\.Python\.(3\.\d+)", line)
        if not m:
            continue
        ver = _parse_version(m.group(1))
        if not ver:
            continue
        pkg_id = f"Python.Python.{ver[0]}.{ver[1]}"
        found.append(
            PythonInstall(
                version=ver,
                label=f"winget {pkg_id}",
                source="winget",
                uninstall_cmd=[
                    "winget",
                    "uninstall",
                    "-e",
                    "--id",
                    pkg_id,
                    "--accept-source-agreements",
                    "--silent",
                ],
            ),
        )
    return found


def discover_via_paths() -> list[PythonInstall]:
    found: list[PythonInstall] = []
    patterns = [
        r"D:\Python\Python*\python.exe",
        r"C:\Python*\python.exe",
        str(Path.home() / "AppData/Local/Programs/Python/Python*/python.exe"),
    ]
    seen: set[str] = set()
    for pattern in patterns:
        for exe in glob.glob(pattern):
            if WINDOWS_APPS in exe.lower():
                continue
            key = exe.lower()
            if key in seen:
                continue
            seen.add(key)
            ver = _python_version_from_exe(exe)
            if not ver:
                continue
            found.append(
                PythonInstall(
                    version=ver,
                    label=f"path {exe}",
                    source="path",
                    path=exe,
                ),
            )
    return found


def merge_installs(items: list[PythonInstall]) -> list[PythonInstall]:
    by_ver: dict[tuple[int, int], PythonInstall] = {}
    for item in items:
        cur = by_ver.get(item.version)
        if cur is None:
            by_ver[item.version] = item
            continue
        if item.source == "winget" and cur.source != "winget":
            by_ver[item.version] = item
    return sorted(by_ver.values(), key=lambda x: x.version)


def uninstall_path_install(item: PythonInstall, dry_run: bool) -> bool:
    if item.uninstall_cmd:
        return run_uninstall(item, dry_run)
    pkg_id = f"Python.Python.{item.version[0]}.{item.version[1]}"
    item.uninstall_cmd = [
        "winget",
        "uninstall",
        "-e",
        "--id",
        pkg_id,
        "--accept-source-agreements",
        "--silent",
    ]
    try:
        proc = _run(["winget", "list", "-e", "--id", pkg_id], timeout=60)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        proc = _ProcResult(1, "", "")

    if pkg_id in _output(proc):
        return run_uninstall(item, dry_run)
    print(f"  [MANUAL] Remove folder and PATH entry: {item.path or item.label}")
    return False


def run_uninstall(item: PythonInstall, dry_run: bool) -> bool:
    if not item.uninstall_cmd:
        return False
    cmd_str = " ".join(item.uninstall_cmd)
    if dry_run:
        print(f"  [DRY-RUN] would run: {cmd_str}")
        return True
    print(f"  Uninstalling: {cmd_str}")
    try:
        proc = subprocess.run(item.uninstall_cmd, timeout=300)
        if proc.returncode == 0:
            print("  [OK] removed")
            return True
        print(f"  [WARN] exit code {proc.returncode}")
        return False
    except (subprocess.TimeoutExpired, OSError) as exc:
        print(f"  [FAIL] {exc}")
        return False


def print_aliases_hint() -> None:
    print()
    print("Also disable Microsoft Store Python stubs:")
    print("  Settings > Apps > Advanced > App execution aliases")
    print("  Turn OFF python.exe and python3.exe")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Uninstall old Python versions; keep 3.9–3.11 for MiniQMT/xtquant.",
    )
    parser.add_argument(
        "--keep",
        default="3.9,3.10,3.11",
        help="Comma-separated versions to keep (default: 3.9,3.10,3.11)",
    )
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Do not ask for confirmation",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only show what would be removed",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List detected Python versions and exit",
    )
    args = parser.parse_args()

    keep: set[tuple[int, int]] = set()
    for part in args.keep.split(","):
        part = part.strip()
        if not part:
            continue
        ver = _parse_version(part if part.startswith("3.") else f"3.{part}")
        if ver:
            keep.add(ver)
    if not keep:
        keep = set(DEFAULT_KEEP)

    all_items = merge_installs(
        discover_via_winget()
        + discover_via_py_launcher()
        + discover_via_paths(),
    )

    if not all_items:
        print("No Python installations detected (excluding WindowsApps stubs).")
        print("Install Python 3.9: scripts\\install_python39.cmd")
        print_aliases_hint()
        return 1

    print("Detected Python installations:")
    for item in all_items:
        tag = "KEEP" if _should_keep(item.version, frozenset(keep)) else "REMOVE"
        print(f"  [{tag}] {item.version[0]}.{item.version[1]} — {item.label}")

    to_remove = [i for i in all_items if not _should_keep(i.version, frozenset(keep))]

    if args.list:
        return 0

    if not to_remove:
        print()
        print("Nothing to remove. Kept versions:", ", ".join(f"{a}.{b}" for a, b in sorted(keep)))
        print_aliases_hint()
        return 0

    print()
    print(f"Will remove {len(to_remove)} old version(s); keep: {', '.join(f'{a}.{b}' for a, b in sorted(keep))}")
    for item in to_remove:
        print(f"  - {item.version[0]}.{item.version[1]} ({item.label})")

    if not args.dry_run and not args.yes:
        print()
        try:
            ans = input("Continue? [y/N]: ").strip().lower()
        except EOFError:
            ans = "n"
        if ans not in ("y", "yes"):
            print("Cancelled.")
            return 0

    print()
    ok = 0
    for item in to_remove:
        print(f"Removing Python {item.version[0]}.{item.version[1]}...")
        if run_uninstall(item, args.dry_run) or args.dry_run:
            ok += 1
        elif item.source == "path" or item.path:
            uninstall_path_install(item, args.dry_run)

    print()
    if args.dry_run:
        print("Dry run complete. Re-run with --yes to uninstall.")
    else:
        print(f"Done. Processed {ok}/{len(to_remove)} uninstall(s).")
        print("Re-run: scripts\\setup_env.cmd")
    print_aliases_hint()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
