from fastapi import FastAPI

from src.api.router import api_router
from src.core.lifespan import lifespan


def create_app() -> FastAPI:
    application = FastAPI(
        title="AI-First Helpdesk Assistant",
        version="0.1.0",
        lifespan=lifespan,
    )
    application.include_router(api_router)
    return application


app = create_app()
