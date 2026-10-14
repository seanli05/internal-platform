"""API tests for Milestone 4: roles, approval, and ownership.

401 = "who are you?" failed (authentication).
403 = "you may not" (authorization): we know who you are, and the answer is no.
"""

import pytest

from app import models
from app.models import Role, Status
from conftest import auth_header, make_user


def upload(client, png_bytes, token):
    r = client.post("/photos", files={"file": ("a.png", png_bytes, "image/png")}, headers=auth_header(token))
    assert r.status_code == 200, r.text
    return r.json()["id"]


@pytest.fixture
def pending(db):
    return make_user(db, "pending@example.com", status=Status.PENDING)


@pytest.fixture
def member(db):
    return make_user(db, "member@example.com")


@pytest.fixture
def other_member(db):
    return make_user(db, "other@example.com")


@pytest.fixture
def exec_(db):  # trailing underscore: `exec` is a Python builtin
    return make_user(db, "exec@example.com", role=Role.EXEC)


@pytest.fixture
def admin(db):
    return make_user(db, "admin@example.com", role=Role.ADMIN)


# --- pending users -----------------------------------------------------------


def test_pending_user_can_see_their_own_status(client, pending):
    _, token = pending
    r = client.get("/users/me", headers=auth_header(token))
    assert r.status_code == 200
    assert r.json()["status"] == "pending"


@pytest.mark.parametrize(
    "method, path",
    [("get", "/photos"), ("post", "/photos"), ("get", "/photos/1/file"), ("delete", "/photos/1")],
)
def test_pending_user_is_403_on_photo_routes(client, pending, method, path):
    _, token = pending
    r = client.request(method, path, headers=auth_header(token))
    assert r.status_code == 403
    assert r.json()["detail"] == "Account awaiting approval"


def test_approval_takes_effect_with_the_same_token(client, pending, exec_):
    # Status is read from the DB on every request, not baked into the token,
    # so the pending user doesn't need to log in again after approval.
    user, token = pending
    assert client.get("/photos", headers=auth_header(token)).status_code == 403

    r = client.post(f"/users/{user.id}/approve", headers=auth_header(exec_[1]))
    assert r.status_code == 200
    assert r.json()["status"] == "approved"

    assert client.get("/photos", headers=auth_header(token)).status_code == 200


# --- approval queue ----------------------------------------------------------


def test_exec_can_list_pending_users(client, pending, member, exec_):
    r = client.get("/users", params={"status": "pending"}, headers=auth_header(exec_[1]))
    assert r.status_code == 200
    assert [u["email"] for u in r.json()] == ["pending@example.com"]


def test_member_cannot_list_or_approve_users(client, pending, member):
    _, token = member
    assert client.get("/users", headers=auth_header(token)).status_code == 403
    assert client.post(f"/users/{pending[0].id}/approve", headers=auth_header(token)).status_code == 403


def test_user_routes_need_a_token(client):
    assert client.get("/users").status_code == 401
    assert client.get("/users/me").status_code == 401


def test_approving_unknown_user_is_404(client, exec_):
    assert client.post("/users/9999/approve", headers=auth_header(exec_[1])).status_code == 404


# --- deleting photos ---------------------------------------------------------


def test_owner_can_delete_own_photo(client, db, member, png_bytes):
    _, token = member
    photo_id = upload(client, png_bytes, token)
    assert client.delete(f"/photos/{photo_id}", headers=auth_header(token)).status_code == 204
    assert db.get(models.Photo, photo_id) is None


def test_member_cannot_delete_someone_elses_photo(client, db, member, other_member, png_bytes):
    photo_id = upload(client, png_bytes, member[1])
    r = client.delete(f"/photos/{photo_id}", headers=auth_header(other_member[1]))
    assert r.status_code == 403
    assert db.get(models.Photo, photo_id) is not None


@pytest.mark.parametrize("moderator", ["exec_", "admin"])
def test_exec_and_admin_can_delete_any_photo(client, db, member, png_bytes, moderator, request):
    # request.getfixturevalue looks up a fixture by name, so one test body
    # covers both roles.
    _, mod_token = request.getfixturevalue(moderator)
    photo_id = upload(client, png_bytes, member[1])
    assert client.delete(f"/photos/{photo_id}", headers=auth_header(mod_token)).status_code == 204
    assert db.get(models.Photo, photo_id) is None


def test_delete_without_token_is_401(client):
    assert client.delete("/photos/1").status_code == 401


# --- changing roles ----------------------------------------------------------


def test_admin_can_change_a_role(client, member, admin):
    user, _ = member
    r = client.post(f"/users/{user.id}/role", data={"role": "exec"}, headers=auth_header(admin[1]))
    assert r.status_code == 200
    assert r.json()["role"] == "exec"


def test_exec_cannot_change_roles(client, member, exec_):
    r = client.post(f"/users/{member[0].id}/role", data={"role": "admin"}, headers=auth_header(exec_[1]))
    assert r.status_code == 403


def test_admin_cannot_change_own_role(client, admin):
    user, token = admin
    r = client.post(f"/users/{user.id}/role", data={"role": "member"}, headers=auth_header(token))
    assert r.status_code == 403


def test_unknown_role_is_rejected(client, member, admin):
    r = client.post(f"/users/{member[0].id}/role", data={"role": "superuser"}, headers=auth_header(admin[1]))
    assert r.status_code == 422


def test_promotion_takes_effect_with_the_same_token(client, member, admin):
    user, token = member
    assert client.get("/users", headers=auth_header(token)).status_code == 403
    client.post(f"/users/{user.id}/role", data={"role": "exec"}, headers=auth_header(admin[1]))
    assert client.get("/users", headers=auth_header(token)).status_code == 200
