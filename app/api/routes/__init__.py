from fastapi import APIRouter

from app.api.routes import auth, documents, schemas


def get_api_router() -> APIRouter:
    router = APIRouter(prefix="/api")
    router.include_router(auth.router)
    router.include_router(documents.router)
    router.include_router(schemas.router)
    return router
