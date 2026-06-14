from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import router
from src.api.middleware import RequestLoggingMiddleware
from src.config.settings import get_settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info("Starting AdOps Copilot API...")
    # Initialize connections here
    yield
    logger.info("Shutting down AdOps Copilot API...")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="AdOps Copilot API",
        description="AI-powered AdOps troubleshooting copilot",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestLoggingMiddleware)
    app.include_router(router, prefix="/api/v1")
    return app


app = create_app()
