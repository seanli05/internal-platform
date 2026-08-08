"""FastAPI application factory and entrypoint (`uvicorn app.main:app`)."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import Settings, get_settings
from app.db import create_database_engine, create_session_factory
from app.logging_config import configure_logging
from app.routers import health

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Own the database engine for the lifetime of the application."""
    settings: Settings = app.state.settings
    engine = create_database_engine(settings)
    app.state.db_engine = engine
    app.state.db_session_factory = create_session_factory(engine)
    logger.info(
        "API started (environment=%s, dev_mode=%s)", settings.environment, settings.dev_mode
    )
    try:
        yield
    finally:
        await engine.dispose()
        logger.info("API stopped; database engine disposed")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the application. Tests use this to get an isolated instance."""
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.state.settings = settings
    app.include_router(health.router)
    return app


app = create_app()
