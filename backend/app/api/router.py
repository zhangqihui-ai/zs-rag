from fastapi import APIRouter

from app.api.routes.auth import router as auth_router
from app.api.routes.enterprise_space import router as enterprise_space_router
from app.api.routes.users import router as users_router
from app.api.routes.graph_visualization import router as graph_visualization_router
from app.api.routes.knowledge_base import router as knowledge_base_router
from app.api.routes.model_management import router as model_management_router
from app.api.routes.system import router as system_router
from app.api.routes.chats import router as chats_router
from app.api.routes.agentic_rag import router as agentic_rag_router
from app.api.routes.platform_audit import router as platform_audit_router
from app.api.routes.chat_completions import openai_router as openai_chat_router
from app.api.routes.chat_completions import router as chat_completions_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(enterprise_space_router)
api_router.include_router(users_router)
api_router.include_router(knowledge_base_router)
api_router.include_router(graph_visualization_router)
api_router.include_router(model_management_router)
api_router.include_router(system_router)
api_router.include_router(chats_router, prefix="/api/v1/chats")
api_router.include_router(agentic_rag_router, prefix="/api/v1/agentic-rag")
api_router.include_router(platform_audit_router)
api_router.include_router(chat_completions_router, prefix="/api/v1/chat")
api_router.include_router(openai_chat_router, prefix="/api/v1/openai")
