from fastapi import APIRouter

from app.api.routes.auth import router as auth_router
from app.api.routes.enterprise_space import router as enterprise_space_router
from app.api.routes.knowledge_base import router as knowledge_base_router
from app.api.routes.model_management import router as model_management_router
from app.api.routes.system import router as system_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(enterprise_space_router)
api_router.include_router(knowledge_base_router)
api_router.include_router(model_management_router)
api_router.include_router(system_router)
