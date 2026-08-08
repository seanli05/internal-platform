"""Shared test fixtures.

The health test talks to a real database on purpose — `GET /health` exists to
report real connectivity, and a mocked "connection" would assert nothing. Start
Postgres first (`docker compose up -d postgres`); CI runs one as a service.
"""

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import create_app


@pytest.fixture(scope="session")
def settings() -> Settings:
    """Settings read from the environment (or `.env`), as the app would."""
    return get_settings()


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    """A fresh application instance per test."""
    return create_app(settings)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    """A test client that runs the app's lifespan (so the DB engine exists)."""
    with TestClient(app) as test_client:
        yield test_client
