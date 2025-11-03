from fastapi import APIRouter

from app.api.routes import analytics, auth, documents, schemas, folders, models, config, users


def get_api_router() -> APIRouter:
    router = APIRouter(prefix="/api")
    router.include_router(auth.router)
    router.include_router(documents.router)
    router.include_router(schemas.router)
    router.include_router(folders.router)
    router.include_router(models.router)
    router.include_router(config.router)
    router.include_router(analytics.router)
    router.include_router(users.router)
    return router
