from fastapi import APIRouter

from app.core.config import settings

router = APIRouter()


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "clinical-data-system"}


@router.get("/version")
def version() -> dict[str, str]:
    return {"version": settings.app_version}

