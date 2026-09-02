from __future__ import annotations

from app.config import (
    ENV_FILE,
    FACTOR_H5,
    PG_EXPORT,
    QLIB_CN_DATA,
    RDAGENT_ROOT,
    SCRIPTS_ROOT,
    VENV_PYTHON,
    VENV_RDAGENT,
)


def _docker_running() -> bool:
    import subprocess

    try:
        r = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=3,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )
        return r.returncode == 0
    except Exception:
        return False


def _env_has_llm_key() -> bool:
    if not ENV_FILE.is_file():
        return False
    text = ENV_FILE.read_text(encoding="utf-8", errors="replace")
    keys = (
        "OPENAI_API_KEY=",
        "DEEPSEEK_API_KEY=",
        "LITELLM_PROXY_API_KEY=",
        "EMBEDDING_OPENAI_API_KEY=",
    )
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("#") or "=" not in s:
            continue
        for k in keys:
            if s.startswith(k) and len(s.split("=", 1)[1].strip()) > 0:
                return True
    return False


def _calendar_span(cal_path):
    if not cal_path.is_file():
        return None
    lines = [ln.strip() for ln in cal_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if not lines:
        return None
    return {"days": len(lines), "from": lines[0], "to": lines[-1]}


def collect_health() -> dict:
    cn_cal = QLIB_CN_DATA / "calendars" / "day.txt"
    export_meta = PG_EXPORT / "export_meta.json"
    export_info = None
    if export_meta.is_file():
        import json

        try:
            export_info = json.loads(export_meta.read_text(encoding="utf-8"))
        except Exception:
            export_info = {"error": "invalid export_meta.json"}

    checks = [
        {
            "id": "venv",
            "title": "RD-Agent 虚拟环境",
            "ok": VENV_PYTHON.is_file() and VENV_RDAGENT.is_file(),
            "hint": "运行 tradeSystem\\scripts\\rdagent_setup.cmd",
            "detail": str(RDAGENT_ROOT / ".venv"),
        },
        {
            "id": "env_file",
            "title": ".env 配置文件",
            "ok": ENV_FILE.is_file(),
            "hint": "复制 rdagent\\.env.example 为 .env 并填写 LLM Key",
            "detail": str(ENV_FILE),
        },
        {
            "id": "llm_key",
            "title": "LLM API Key",
            "ok": _env_has_llm_key(),
            "hint": "在 rdagent\\.env 填写 OPENAI_API_KEY / DEEPSEEK_API_KEY 等",
            "detail": "已检测密钥字段" if _env_has_llm_key() else "未检测到非空密钥",
        },
        {
            "id": "docker",
            "title": "Docker Desktop",
            "ok": _docker_running(),
            "hint": "启动 Docker Desktop（fin_factor 回测需要）",
            "detail": "docker info",
        },
        {
            "id": "cn_data",
            "title": "官方 Qlib cn_data",
            "ok": cn_cal.is_file(),
            "hint": "运行「下载官方数据」或 scripts\\rdagent_download_qlib.cmd",
            "detail": str(QLIB_CN_DATA),
            "extra": _calendar_span(cn_cal),
        },
        {
            "id": "factor_h5",
            "title": "预生成因子 HDF5",
            "ok": FACTOR_H5.is_file(),
            "hint": "运行「预生成因子数据」可避免 Docker 首次卡很久",
            "detail": str(FACTOR_H5),
        },
        {
            "id": "pg_export",
            "title": "PG→Qlib 导出样本",
            "ok": (PG_EXPORT / "csv").is_dir() and any((PG_EXPORT / "csv").glob("*.csv")),
            "hint": "可选：scripts\\export_pg_qlib.cmd（与生产 PG 对齐）",
            "detail": str(PG_EXPORT),
            "extra": export_info,
        },
        {
            "id": "scripts",
            "title": "启动脚本目录",
            "ok": (SCRIPTS_ROOT / "rdagent_fin_factor.cmd").is_file(),
            "hint": "确认 tradeSystem\\scripts 完整",
            "detail": str(SCRIPTS_ROOT),
        },
    ]

    ready_to_learn = all(c["ok"] for c in checks if c["id"] in ("venv", "env_file", "scripts"))
    ready_to_run = all(
        c["ok"] for c in checks if c["id"] in ("venv", "env_file", "llm_key", "docker", "cn_data")
    )

    return {
        "ready_to_learn": ready_to_learn,
        "ready_to_run": ready_to_run,
        "checks": checks,
        "paths": {
            "tradesystem": str(RDAGENT_ROOT.parent),
            "rdagent": str(RDAGENT_ROOT),
            "scripts": str(SCRIPTS_ROOT),
            "cn_data": str(QLIB_CN_DATA),
            "pg_export": str(PG_EXPORT),
        },
    }