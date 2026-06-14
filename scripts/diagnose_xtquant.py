"""Diagnose xtquant / IPythonApiClient import issues on Windows."""

from __future__ import annotations

import glob
import os
import struct
import sys
from pathlib import Path


def _pe_imports(pyd_path: Path) -> list[str]:
    data = pyd_path.read_bytes()
    if data[:2] != b"MZ":
        return []
    pe_off = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe_off : pe_off + 4] != b"PE\0\0":
        return []
    num_sections = struct.unpack_from("<H", data, pe_off + 6)[0]
    opt_hdr_size = struct.unpack_from("<H", data, pe_off + 20)[0]
    opt_off = pe_off + 24
    magic = struct.unpack_from("<H", data, opt_off)[0]
    if magic == 0x20B:
        import_rva, import_size = struct.unpack_from("<II", data, opt_off + 112)
    elif magic == 0x10B:
        import_rva, import_size = struct.unpack_from("<II", data, opt_off + 96)
    else:
        return []

    def rva_to_offset(rva: int) -> int:
        sec_off = opt_off + opt_hdr_size
        for _ in range(num_sections):
            vsize, vaddr, raw_size, raw_ptr = struct.unpack_from(
                "<IIII", data, sec_off + 8
            )
            if vaddr <= rva < vaddr + max(vsize, raw_size):
                return raw_ptr + (rva - vaddr)
            sec_off += 40
        return 0

    imports: list[str] = []
    off = rva_to_offset(import_rva)
    while off and off + 20 <= len(data):
        _, _, _, name_rva, _ = struct.unpack_from("<IIIII", data, off)
        if name_rva == 0:
            break
        name_off = rva_to_offset(name_rva)
        end = data.find(b"\0", name_off)
        if end == -1:
            break
        imports.append(data[name_off:end].decode("ascii", errors="replace"))
        off += 20
    return imports


def main() -> int:
    print("Python:", sys.version.replace("\n", " "))
    print("Executable:", sys.executable)
    print("Arch:", struct.calcsize("P") * 8, "bit")

    root = os.environ.get("QMT_ROOT", r"D:\gjqmt")
    bin_x64 = Path(root) / "bin.x64"
    xt_dir = bin_x64 / "Lib" / "site-packages" / "xtquant"
    print("QMT_ROOT:", root)
    print("xtquant dir exists:", xt_dir.is_dir())

    py_tag = f"cp{sys.version_info.major}{sys.version_info.minor}"
    pyd = xt_dir / f"IPythonApiClient.{py_tag}-win_amd64.pyd"
    print("Expected pyd:", pyd.name, "exists:", pyd.is_file())

    if pyd.is_file():
        deps = _pe_imports(pyd)
        print("IPythonApiClient imports:", ", ".join(deps) if deps else "(none parsed)")
        for dll in deps:
            if not dll.lower().endswith(".dll"):
                continue
            found = list(bin_x64.glob(dll)) + list(xt_dir.glob(dll))
            py_dir = Path(sys.executable).parent
            found += list(py_dir.glob(dll))
            status = str(found[0]) if found else "MISSING"
            print(f"  {dll}: {status}")

    print()
    print("Import test ...")
    try:
        from minqmt.qmt_bootstrap import configure_qmt

        configure_qmt()
        from xtquant import xtdata  # noqa: F401

        print("[OK] xtquant import succeeded")
        return 0
    except Exception as exc:
        print("[FAIL]", exc)
        tag = sys.version_info.major, sys.version_info.minor
        if tag == (3, 8):
            print()
            print("Known issue: some QMT builds ship a broken cp38 pyd")
            print("that imports python27.dll instead of python38.dll.")
            print("Fix: install Python 3.9/3.10/3.11 and re-run setup_env.ps1,")
            print("or re-download xtquant from QMT: Settings > Model > Python library.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
