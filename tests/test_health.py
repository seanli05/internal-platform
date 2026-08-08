"""`GET /health` must reflect real database connectivity."""

from collections.abc import AsyncIterator
from typing import Any, cast

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session


class _UnreachableSession:
    """Stands in for a session whose connection attempt fails."""

    async def execute(self, *_args: Any, **_kwargs: Any) -> Any:
        raise OperationalError("SELECT 1", params=None, orig=OSError("connection refused"))


def test_health_returns_ok_when_database_is_reachable(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_returns_503_when_database_is_unreachable(app: FastAPI) -> None:
    """A database that will not answer must surface as 503, never as 200."""

    async def unreachable_session() -> AsyncIterator[AsyncSession]:
        yield cast(AsyncSession, _UnreachableSession())

    app.dependency_overrides[get_session] = unreachable_session
    try:
        with TestClient(app) as client:
            response = client.get("/health")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json()["detail"] == "Database unavailable"
