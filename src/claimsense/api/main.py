from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from claimsense.api.routers.claims import router as claims_router
from claimsense.api.routers.health import router as health_router
from claimsense.core.config import get_settings
from claimsense.core.logging import configure_logging
from claimsense.reasoning.orchestrator import ClaimAnalysisOrchestrator, KnowledgeBase

logger = logging.getLogger(__name__)


def bootstrap_application_state(app: FastAPI) -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    knowledge_base = KnowledgeBase(settings.knowledge_dir)
    app.state.knowledge_base = knowledge_base
    app.state.orchestrator = ClaimAnalysisOrchestrator(knowledge_base)


@asynccontextmanager
async def lifespan(app: FastAPI):
    bootstrap_application_state(app)
    logger.info("Application startup complete")
    yield
    logger.info("Application shutdown complete")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        root_path=settings.root_path,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )
    bootstrap_application_state(app)
    app.include_router(health_router)
    app.include_router(claims_router)

    @app.exception_handler(ValueError)
    async def value_error_handler(_, exc: ValueError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    return app


app = create_app()
