# DSS

Photo backend. Milestone 1: store a photo, list photos back.

## Run

```bash
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
cp .env.example .env   # then fill in SECRET_KEY (command is in the file)
alembic upgrade head   # create/update the database schema
uvicorn app.main:app --reload
```

New accounts start **pending**. Bootstrap the first admin after registering:

```bash
python -m scripts.make_admin you@example.com
```

Then open http://127.0.0.1:8000/docs and exercise the endpoints from there.

## Layout

```
app/
  config.py   SECRET_KEY from .env                  (settings)
  db.py       engine + session factory + Base       (infrastructure)
  models.py   SQLAlchemy tables                     (storage contract)
  schemas.py  Pydantic request/response shapes      (API contract)
  main.py     FastAPI app + photo routes            (transport)
  auth.py     /auth/register, /auth/login           (throwaway: password proof)
  passwords.py bcrypt hash/verify                   (throwaway: password proof)
  tokens.py   mint JWT + get_current_user           (permanent: who are you? → 401)
  permissions.py require_role                        (permanent: may you? → 403)
  users.py    /users/me, approval queue, roles      (permanent)
migrations/   Alembic schema migrations — see docs/migrations.md
tests/        pytest suite (uv pip install -r requirements-dev.txt; uv run pytest)
uploads/      photo bytes on disk (gitignored)
photos.db     SQLite file (gitignored)
```

Bytes live on disk; rows in the database point at them.

## API

| Method | Path             | Auth   | Body                          | Returns                      |
| ------ | ---------------- | ------ | ----------------------------- | ---------------------------- |
| POST   | `/auth/register` | —      | form: `email`, `password`     | the new user (201)           |
| POST   | `/auth/login`    | —      | form: `email`, `password`     | `{access_token, token_type}` |
| GET    | `/users/me`      | Bearer (pending OK) | —                | your user, incl. role/status |
| GET    | `/users`         | exec+  | `?status=pending` optional    | list of users                |
| POST   | `/users/{id}/approve` | exec+ | —                         | the approved user            |
| POST   | `/users/{id}/role` | admin (not self) | form: `role`       | the updated user             |
| POST   | `/photos`        | member+ | `multipart/form-data`        | the new photo                |
| GET    | `/photos`        | member+ | —                            | list of rows                 |
| GET    | `/photos/{id}/file` | member+ | —                         | the image bytes              |
| DELETE | `/photos/{id}`   | owner, or exec+ | —                    | 204                          |

"member+" means an **approved** user with at least that role (member < exec < admin).
