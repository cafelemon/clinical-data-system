from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    clinical_data,
    dashboard,
    excel_io,
    files,
    health,
    identity,
    image_data,
    master_data,
    operation_logs,
    pdf_packets,
    pdf_review,
    reviews,
    system_management,
    trial_protocols,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["system"])
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(identity.router, tags=["identity"])
api_router.include_router(image_data.router, tags=["image-data"])
api_router.include_router(master_data.router, tags=["master-data"])
api_router.include_router(clinical_data.router, tags=["clinical-data"])
api_router.include_router(files.router, tags=["files"])
api_router.include_router(pdf_packets.router, tags=["pdf-packets"])
api_router.include_router(pdf_review.router, tags=["pdf-review"])
api_router.include_router(reviews.router, tags=["reviews"])
api_router.include_router(dashboard.router, tags=["dashboard"])
api_router.include_router(excel_io.router, tags=["excel-io"])
api_router.include_router(operation_logs.router, tags=["operation-logs"])
api_router.include_router(trial_protocols.router, tags=["trial-protocols"])
api_router.include_router(system_management.router, tags=["system-management"])
