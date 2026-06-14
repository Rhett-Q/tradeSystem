from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from services.health_service import get_health

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health")
def health() -> dict[str, Any]:
    return get_health()
