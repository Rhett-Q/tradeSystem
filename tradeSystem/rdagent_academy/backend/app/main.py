"""RD-Agent Academy API — standalone learning + ops console."""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.config import FRONTEND_ORIGIN, HOST, PORT
from app.services import content_service, health_service, session_service
from app.services.job_service import JOB_CATALOG, job_manager, start_streamlit_ui

app = FastAPI(title="RD-Agent Academy", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN, "http://localhost:19901", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class StartJobBody(BaseModel):
    kind: str = Field(..., description="Job kind from catalog")
    meta: Dict[str, Any] = Field(default_factory=dict)


class OpenUiBody(BaseModel):
    log_path: Optional[str] = None


@app.get("/api/health")
def api_health():
    return health_service.collect_health()


@app.get("/api/curriculum")
def api_curriculum():
    return content_service.curriculum()


@app.get("/api/lessons/{lesson_id}")
def api_lesson(lesson_id: str):
    try:
        return content_service.lesson(lesson_id)
    except FileNotFoundError:
        raise HTTPException(404, f"lesson not found: {lesson_id}") from None


@app.get("/api/jobs/catalog")
def api_job_catalog():
    return {
        "jobs": [
            {"kind": k, "title": v["title"], "exclusive": bool(v.get("exclusive"))}
            for k, v in JOB_CATALOG.items()
        ]
    }


@app.get("/api/jobs")
def api_jobs():
    return {"jobs": job_manager.list_jobs()}


@app.post("/api/jobs")
def api_start_job(body: StartJobBody):
    try:
        job = job_manager.start(body.kind, body.meta)
        return job_manager._public(job)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.get("/api/jobs/{job_id}")
def api_job(job_id: str, from_line: int = Query(0, ge=0)):
    job = job_manager.get(job_id)
    if not job:
        raise HTTPException(404, "job not found")
    return job_manager.public_with_log(job, from_line)


@app.post("/api/jobs/{job_id}/cancel")
def api_cancel_job(job_id: str):
    try:
        job = job_manager.cancel(job_id)
        return job_manager._public(job)
    except KeyError:
        raise HTTPException(404, "job not found") from None
    except RuntimeError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/api/sessions")
def api_sessions():
    return {"sessions": session_service.list_sessions(), "latest": session_service.latest_status()}


@app.get("/api/sessions/{log_id}")
def api_session_detail(log_id: str):
    try:
        return session_service.session_feedback(log_id)
    except FileNotFoundError:
        raise HTTPException(404, "session not found") from None


@app.post("/api/ui/streamlit")
def api_open_streamlit(body: OpenUiBody):
    try:
        return start_streamlit_ui(body.log_path)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.get("/api/meta")
def api_meta():
    return {
        "name": "RD-Agent Academy",
        "tagline": "从零学会用 RD-Agent 做因子演化",
        "host": HOST,
        "port": PORT,
        "related": {
            "streamlit_ui": "http://localhost:19899",
            "tradesystem": "http://127.0.0.1:5173",
            "docs": "https://rdagent.readthedocs.io/",
            "github": "https://github.com/microsoft/RD-Agent",
        },
    }


def main() -> None:
    import uvicorn

    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=False)


if __name__ == "__main__":
    main()