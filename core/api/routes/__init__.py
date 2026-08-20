from fastapi import APIRouter

from .documents import router as documents_router
from .eval import router as eval_router
from .health import router as health_router
from .search import router as search_router
from .upload import router as upload_router

api_router = APIRouter()

api_router.include_router(health_router)
api_router.include_router(upload_router)
api_router.include_router(documents_router)
api_router.include_router(search_router)
api_router.include_router(eval_router)
