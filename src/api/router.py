from fastapi import APIRouter

from src.api.v1.mock_helpdesk import router as mock_helpdesk_router
from src.api.v1.webhooks import router as webhooks_router
from src.api.web.moderation import router as moderation_router

api_router = APIRouter()
api_router.include_router(webhooks_router)
api_router.include_router(mock_helpdesk_router)
api_router.include_router(moderation_router)
