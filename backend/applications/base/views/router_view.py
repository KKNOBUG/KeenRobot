from fastapi import APIRouter

from backend.applications.user.views import auth_router
from backend.applications.conversation.views import chat_router, history_router
from backend.applications.knowledge_base.views import kb_router
from backend.applications.model_config.views import model_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(chat_router)
api_router.include_router(history_router)
api_router.include_router(kb_router)
api_router.include_router(model_router)
