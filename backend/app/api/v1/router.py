from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    clinical_data,
    dashboard,
    files,
    health,
    identity,
    master_data,
    reviews,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["system"])
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(identity.router, tags=["identity"])
api_router.include_router(master_data.router, tags=["master-data"])
api_router.include_router(clinical_data.router, tags=["clinical-data"])
api_router.include_router(files.router, tags=["files"])
api_router.include_router(reviews.router, tags=["reviews"])
api_router.include_router(dashboard.router, tags=["dashboard"])
