from fastapi import APIRouter

from app.api.v1.endpoints import auth, health, identity, master_data

api_router = APIRouter()
api_router.include_router(health.router, tags=["system"])
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(identity.router, tags=["identity"])
api_router.include_router(master_data.router, tags=["master-data"])
