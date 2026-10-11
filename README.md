# DSS

Photo backend. Milestone 1: store a photo, list photos back.

## Run

```bash
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
cp .env.example .env   # then fill in SECRET_KEY (command is in the file)
uvicorn app.main:app --reload
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
  tokens.py   mint JWT + get_current_user           (permanent: token spine)
uploads/      photo bytes on disk (gitignored)
dss.db        SQLite file (gitignored)
```

Bytes live on disk; rows in the database point at them.

## API

| Method | Path             | Auth   | Body                          | Returns                      |
| ------ | ---------------- | ------ | ----------------------------- | ---------------------------- |
| POST   | `/auth/register` | —      | form: `email`, `password`     | the new user (201)           |
| POST   | `/auth/login`    | —      | form: `email`, `password`     | `{access_token, token_type}` |
| POST   | `/photos`        | Bearer | `multipart/form-data`         | the new photo                |
| GET    | `/photos`        | —      | —                             | list of rows                 |
