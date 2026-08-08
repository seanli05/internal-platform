"""Database engine, session factory, and the request-scoped session dependency.

The engine is created per-application-instance during the lifespan (not at import
time) and stored on `app.state`. That keeps it bound to the running event loop and
lets tests spin up an app without touching a real database.
"""

from collections.abc import AsyncIterator

from fastapi import FastAPI, Request
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import Settings


def create_database_engine(settings: Settings) -> AsyncEngine:
    """Create the async engine for the given settings."""
    return create_async_engine(
        str(settings.database_url),
        pool_pre_ping=True,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create the session factory bound to `engine`."""
    return async_sessionmaker(engine, expire_on_commit=False)


def get_session_factory(app: FastAPI) -> async_sessionmaker[AsyncSession]:
    """Return the session factory stored on the app during startup."""
    factory: async_sessionmaker[AsyncSession] | None = getattr(
        app.state, "db_session_factory", None
    )
    if factory is None:  # pragma: no cover - only reachable if lifespan did not run
        raise RuntimeError("Database session factory is not configured; did the lifespan run?")
    return factory


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding a session for the duration of one request."""
    session_factory = get_session_factory(request.app)
    async with session_factory() as session:
        yield session
