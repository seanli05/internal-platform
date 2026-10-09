# DSS

Photo backend. Milestone 1: store a photo, list photos back.

## Run

```bash
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
uvicorn app.main:app --reload
```

Then open http://127.0.0.1:8000/docs and exercise the endpoints from there.

## Layout

```
app/
  db.py       engine + session factory + Base       (infrastructure)
  models.py   SQLAlchemy tables                     (storage contract)
  schemas.py  Pydantic request/response shapes      (API contract)
  main.py     FastAPI app + routes                  (transport)
uploads/      photo bytes on disk (gitignored)
dss.db        SQLite file (gitignored)
```

Bytes live on disk; rows in the database point at them.

## API

| Method | Path      | Body                  | Returns       |
| ------ | --------- | --------------------- | ------------- |
| POST   | `/photos` | `multipart/form-data` | the new photo |
| GET    | `/photos` | —                     | list of rows  |
