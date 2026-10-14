"""API tests for the Milestone 3 auth spine.

Each test sends real requests through routing, dependencies and the
database (via TestClient), so it checks how the pieces connect, not just
one function on its own.
"""

from datetime import UTC, datetime, timedelta

import jwt

from app import models
from app.config import SECRET_KEY
from app.tokens import ALGORITHM, create_access_token
from conftest import EMAIL, PASSWORD, auth_header, login, make_user, register


def upload(client, png_bytes, headers=None):
    return client.post("/photos", files={"file": ("a.png", png_bytes, "image/png")}, headers=headers)


# --- register --------------------------------------------------------------


def test_register_stores_a_hash_not_the_password(client, db):
    r = register(client)
    assert r.status_code == 201
    assert r.json()["email"] == EMAIL
    assert "password_hash" not in r.json()
    # New accounts start as pending members.
    assert r.json()["role"] == "member"
    assert r.json()["status"] == "pending"

    user = db.query(models.User).one()
    assert user.password_hash != PASSWORD
    assert user.password_hash.startswith("$2b$")


def test_register_rejects_duplicate_email_case_insensitively(client):
    assert register(client).status_code == 201
    assert register(client, email="  SEAN@Example.com").status_code == 409


def test_register_rejects_short_password(client):
    assert register(client, password="short").status_code == 400


# --- login -----------------------------------------------------------------


def test_login_returns_a_bearer_token(client):
    register(client)
    r = login(client)
    assert r.status_code == 200
    assert r.json()["token_type"] == "bearer"
    assert r.json()["access_token"]


def test_login_failure_does_not_reveal_whether_email_exists(client):
    register(client)
    wrong_password = login(client, password="wrong-password")
    unknown_email = login(client, email="nobody@example.com")

    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()


# --- POST /photos auth -----------------------------------------------------


def test_upload_without_token_is_401(client, png_bytes, tmp_path):
    r = upload(client, png_bytes)
    assert r.status_code == 401
    assert r.headers["WWW-Authenticate"] == "Bearer"
    # Rejected before the handler ran: nothing saved to disk.
    assert list((tmp_path / "uploads").iterdir()) == []


def test_upload_with_garbage_token_is_401(client, png_bytes):
    r = upload(client, png_bytes, auth_header("not.a.jwt"))
    assert r.status_code == 401
    assert r.json()["detail"] == "Invalid token"


def test_upload_with_token_signed_by_another_key_is_401(client, png_bytes, token):
    # Re-sign a real token's payload with the wrong key: a forgery.
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    forged = jwt.encode(payload, "an-attacker-key-that-is-at-least-32-bytes", algorithm=ALGORITHM)
    assert upload(client, png_bytes, auth_header(forged)).status_code == 401


def test_upload_with_expired_token_is_401(client, png_bytes, token):
    payload = {"sub": "1", "exp": datetime.now(UTC) - timedelta(seconds=1)}
    expired = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    r = upload(client, png_bytes, auth_header(expired))
    assert r.status_code == 401
    assert r.json()["detail"] == "Token expired"


def test_upload_for_deleted_user_is_401(client, db, png_bytes, token):
    db.query(models.User).delete()
    db.commit()
    r = upload(client, png_bytes, auth_header(token))
    assert r.status_code == 401
    assert r.json()["detail"] == "User not found"


def test_upload_with_valid_token_records_the_owner(client, db, png_bytes, token):
    r = upload(client, png_bytes, auth_header(token))
    assert r.status_code == 200

    user = db.query(models.User).one()
    photo = db.get(models.Photo, r.json()["id"])
    assert photo.user_id == user.id


def test_token_for_a_specific_user_is_attributed_to_them(client, db, png_bytes):
    # Two users; a token minted for the second must upload as the second.
    make_user(db, "first@example.com")
    second, _ = make_user(db, "second@example.com")

    r = upload(client, png_bytes, auth_header(create_access_token(second.id)))
    assert db.get(models.Photo, r.json()["id"]).user_id == second.id


# --- GET /photos ------------------------------------------------------------


def test_list_photos_requires_a_token(client):
    assert client.get("/photos").status_code == 401


def test_list_photos_with_token(client, png_bytes, token):
    upload(client, png_bytes, auth_header(token))
    r = client.get("/photos", headers=auth_header(token))
    assert r.status_code == 200
    assert len(r.json()) == 1
