"""Curriculum / lesson content loader."""
from __future__ import annotations

import json
from pathlib import Path

from app.config import CONTENT_ROOT


def curriculum() -> dict:
    path = CONTENT_ROOT / "curriculum.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return data


def lesson(lesson_id: str) -> dict:
    data = curriculum()
    found = None
    for track in data.get("tracks", []):
        for item in track.get("lessons", []):
            if item["id"] == lesson_id:
                found = {**item, "track_id": track["id"], "track_title": track["title"]}
                break
    if not found:
        raise FileNotFoundError(lesson_id)

    md_path = CONTENT_ROOT / "lessons" / f"{lesson_id}.md"
    body = md_path.read_text(encoding="utf-8") if md_path.is_file() else "# 内容待补充\n"
    return {**found, "body_markdown": body}