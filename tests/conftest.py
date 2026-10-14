"""Shared test setup: a throwaway database and uploads folder for every test.

pytest loads this file automatically before any test module. Each fixture
below is a function whose return value gets passed to any test that names it
as a parameter (e.g. `def test_x(client, db)`).
"""

import io
import os

# Must run BEFORE anything imports app.config, which refuses to start without
# a key. setdefault + load_dotenv's no-override rule mean tests always use
# this fixed key, never the real one in .env, and also work with no .env.
os.environ.setdefault("SECRET_KEY", "test-secret-key-that-is-at-least-32-bytes-long")

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import main, models
from app.db import Base, get_db
from app.models import Role, Status
from app.passwords import hash_password
from app.tokens import create_access_token


@pytest.fixture
def db(tmp_path):
    """A fresh SQLite file per test, so tests can't affect each other.

    tmp_path is a built-in pytest fixture: a new empty folder per test,
    cleaned up automatically.
    """
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    # Swap the app's get_db for one that hands out sessions on the test DB.
    # Every Depends(get_db), including the one inside get_current_user,
    # now gets the test database instead of photos.db.
    def override_get_db():
        session = TestSession()
        try:
            yield session
        finally:
            session.close()

    main.app.dependency_overrides[get_db] = override_get_db

    # The test's own session, for checking rows directly.
    session = TestSession()
    yield session
    session.close()
    main.app.dependency_overrides.clear()
    engine.dispose()


@pytest.fixture
def client(db, tmp_path, monkeypatch):
    """A TestClient wired to the test DB, saving uploads into tmp_path.

    TestClient calls the app in-process: no server, no network, no port.
    """
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    # monkeypatch swaps main.UPLOAD_DIR for this test only and restores it after.
    monkeypatch.setattr(main, "UPLOAD_DIR", upload_dir)
    return TestClient(main.app)


@pytest.fixture
def png_bytes():
    """A real 1x1 PNG, so it passes the Pillow validation in upload_photo."""
    buf = io.BytesIO()
    Image.new("RGB", (1, 1)).save(buf, format="PNG")
    return buf.getvalue()


# --- helpers ---------------------------------------------------------------

EMAIL = "sean@example.com"
PASSWORD = "correct-horse"


def register(client, email=EMAIL, password=PASSWORD):
    return client.post("/auth/register", data={"email": email, "password": password})


def login(client, email=EMAIL, password=PASSWORD):
    return client.post("/auth/login", data={"email": email, "password": password})


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


def make_user(db, email, role=Role.MEMBER, status=Status.APPROVED):
    """Insert a user directly and return (user, token).

    Skips the HTTP register/login dance so permission tests can set up
    "an approved exec" or "a pending member" in one line.
    """
    user = models.User(email=email, password_hash=hash_password(PASSWORD), role=role, status=status)
    db.add(user)
    db.commit()
    return user, create_access_token(user.id)


@pytest.fixture
def token(client, db):
    """Register + log in the default user, approve them; return their token."""
    register(client)
    db.query(models.User).filter_by(email=EMAIL).update({"status": Status.APPROVED})
    db.commit()
    return login(client).json()["access_token"]
