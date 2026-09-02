"""Background job runner wrapping tradeSystem RD-Agent scripts."""
from __future__ import annotations

import subprocess
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Deque, Dict, Optional

from app.config import RDAGENT_ROOT, SCRIPTS_ROOT, VENV_PYTHON

CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


@dataclass
class Job:
    id: str
    kind: str
    title: str
    status: str = "queued"  # queued|running|succeeded|failed|cancelled
    created_at: str = ""
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    exit_code: Optional[int] = None
    log: Deque[str] = field(default_factory=lambda: deque(maxlen=4000))
    meta: dict = field(default_factory=dict)
    _proc: Optional[subprocess.Popen] = field(default=None, repr=False)


JOB_CATALOG: Dict[str, dict] = {
    "health_cli": {
        "title": "RD-Agent health_check",
        "script": "rdagent_health.cmd",
        "cwd": "tradesystem",
    },
    "download_qlib": {
        "title": "下载官方 Qlib cn_data",
        "script": "rdagent_download_qlib.cmd",
        "cwd": "tradesystem",
    },
    "prepare_factor_data": {
        "title": "预生成因子 HDF5",
        "script": "rdagent_prepare_factor_data.cmd",
        "cwd": "tradesystem",
    },
    "export_pg": {
        "title": "PostgreSQL → Qlib 导出",
        "script": "export_pg_qlib.cmd",
        "cwd": "tradesystem",
    },
    "fin_factor": {
        "title": "启动 fin_factor（新开跑）",
        "script": "rdagent_fin_factor.cmd",
        "cwd": "tradesystem",
        "exclusive": True,
    },
    "resume_factor": {
        "title": "恢复 fin_factor",
        "script": "rdagent_resume_factor.cmd",
        "cwd": "tradesystem",
        "exclusive": True,
    },
}


class JobManager:
    def __init__(self) -> None:
        self._jobs: Dict[str, Job] = {}
        self._lock = threading.Lock()

    def list_jobs(self):
        with self._lock:
            return [self._public(j) for j in sorted(self._jobs.values(), key=lambda x: x.created_at, reverse=True)]

    def get(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    def active_exclusive(self) -> Optional[Job]:
        with self._lock:
            for j in self._jobs.values():
                if j.status == "running" and JOB_CATALOG.get(j.kind, {}).get("exclusive"):
                    return j
        return None

    def start(self, kind: str, meta: Optional[dict] = None) -> Job:
        if kind not in JOB_CATALOG:
            raise ValueError(f"unknown job kind: {kind}")
        spec = JOB_CATALOG[kind]
        if spec.get("exclusive"):
            active = self.active_exclusive()
            if active:
                raise RuntimeError(f"已有任务在运行: {active.title} ({active.id})")

        script = SCRIPTS_ROOT / spec["script"]
        if not script.is_file():
            raise FileNotFoundError(f"script not found: {script}")

        job = Job(
            id=uuid.uuid4().hex[:12],
            kind=kind,
            title=spec["title"],
            created_at=datetime.now(timezone.utc).isoformat(),
            meta=meta or {},
        )
        with self._lock:
            self._jobs[job.id] = job

        thread = threading.Thread(target=self._run, args=(job, script), daemon=True)
        thread.start()
        return job

    def cancel(self, job_id: str) -> Job:
        job = self._jobs.get(job_id)
        if not job:
            raise KeyError(job_id)
        if job.status != "running" or job._proc is None:
            raise RuntimeError("任务未在运行，无法取消")
        job._proc.terminate()
        job.status = "cancelled"
        job.finished_at = datetime.now(timezone.utc).isoformat()
        job.log.append("\n[academy] 已请求终止进程\n")
        return job

    def _run(self, job: Job, script: Path) -> None:
        job.status = "running"
        job.started_at = datetime.now(timezone.utc).isoformat()
        job.log.append(f"[academy] 启动 {script.name}\n")

        try:
            # cmd.exe so .cmd scripts work with delayed expansion etc.
            proc = subprocess.Popen(
                ["cmd.exe", "/c", str(script)],
                cwd=str(SCRIPTS_ROOT.parent),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=CREATE_NO_WINDOW,
            )
            job._proc = proc
            assert proc.stdout is not None
            for line in proc.stdout:
                job.log.append(line)
            proc.wait()
            job.exit_code = proc.returncode
            job.status = "succeeded" if proc.returncode == 0 else "failed"
            # refresh session status after factor runs
            if job.kind in ("fin_factor", "resume_factor") and VENV_PYTHON.is_file():
                try:
                    subprocess.run(
                        [str(VENV_PYTHON), str(SCRIPTS_ROOT / "rdagent_session_status.py"), "--write"],
                        cwd=str(RDAGENT_ROOT),
                        capture_output=True,
                        timeout=60,
                        creationflags=CREATE_NO_WINDOW,
                    )
                    job.log.append("\n[academy] 已刷新 session_status.json\n")
                except Exception as exc:
                    job.log.append(f"\n[academy] 刷新 session 状态失败: {exc}\n")
        except Exception as exc:
            job.status = "failed"
            job.exit_code = -1
            job.log.append(f"\n[academy] 异常: {exc}\n")
        finally:
            job.finished_at = datetime.now(timezone.utc).isoformat()
            job._proc = None

    @staticmethod
    def _public(job: Job) -> dict:
        return {
            "id": job.id,
            "kind": job.kind,
            "title": job.title,
            "status": job.status,
            "created_at": job.created_at,
            "started_at": job.started_at,
            "finished_at": job.finished_at,
            "exit_code": job.exit_code,
            "log_tail": "".join(list(job.log)[-80:]),
            "log_lines": len(job.log),
            "meta": job.meta,
        }

    def public_with_log(self, job: Job, from_line: int = 0) -> dict:
        lines = list(job.log)
        chunk = lines[from_line:]
        data = self._public(job)
        data["log_chunk"] = "".join(chunk)
        data["next_line"] = from_line + len(chunk)
        return data


job_manager = JobManager()


def start_streamlit_ui(log_path: Optional[str] = None) -> dict:
    """Launch official RD-Agent Streamlit UI in a detached process."""
    ui_script = SCRIPTS_ROOT / "rdagent_ui.cmd"
    if not ui_script.is_file():
        raise FileNotFoundError(str(ui_script))

    args = ["cmd.exe", "/c", "start", "RD-Agent UI", "cmd.exe", "/k", str(ui_script)]
    if log_path:
        args.append(log_path.replace("/", "\\"))

    subprocess.Popen(
        args,
        cwd=str(SCRIPTS_ROOT.parent),
        creationflags=CREATE_NO_WINDOW,
    )
    return {
        "ok": True,
        "url": "http://localhost:19899",
        "message": "已在新窗口启动 Streamlit UI（端口 19899）",
        "log_path": log_path,
    }