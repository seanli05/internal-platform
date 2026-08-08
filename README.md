# DSS Internal Platform

Login-walled internal platform for the Data Science Society: a searchable club photo archive (semantic + face search), a member directory, and an exec dashboard.

**Status: Phase 0 (Foundations).** The app runs, talks to Postgres, and has its lint/type/test/CI guardrails in place. No auth, models, or features yet — those arrive phase by phase. See [`docs/BUILD_PLAN.md`](docs/BUILD_PLAN.md) for the plan of record and [`CLAUDE.md`](CLAUDE.md) for the durable constraints.

---

## Architecture

Three processes to keep alive, plus a storage bucket (from Phase 3 on):

| Piece | What it is |
|---|---|
| `api` | FastAPI web process — serves the HTTP API |
| `worker` | Python process, **same codebase**, second entrypoint — processes photos asynchronously |
| `postgres` | Postgres + `pgvector` — the only datastore (member records, CLIP vectors, face vectors) |

```
app/            FastAPI application (config, db, routers, services)
app/worker/     worker entrypoint — shares app/ settings and models
migrations/     Alembic migrations
scripts/        bootstrap + dev seeding scripts (Phase 2)
tests/          pytest
```

## Prerequisites

- [Docker Desktop](https://docs.docker.com/desktop/) (or any Docker with Compose v2)
- [uv](https://docs.astral.sh/uv/) — `brew install uv`
- Python 3.12 (uv installs it for you if it is missing)

## Run it

```bash
git clone <this repo> && cd DSS-internal
cp .env.example .env          # dummy local values; edit if you like
docker compose up             # api + worker + postgres
```

That is the whole setup. Compose runs `alembic upgrade head` before starting the API, so the database is migrated for you.

- API: <http://localhost:8000>
- Health check: <http://localhost:8000/health> → `{"status": "ok"}`
- Interactive API docs: <http://localhost:8000/docs>
- Worker: logs `worker alive` on an interval — `docker compose logs -f worker`

`GET /health` returns **200 only if the database answered a `SELECT 1`**. A 503 means the API is up but Postgres is not reachable.

Stop with `Ctrl-C`. `docker compose down -v` also wipes the database volume.

### Running on the host instead

Handy for fast test and lint loops. Postgres still comes from Compose.

```bash
docker compose up -d postgres
uv sync                                    # create .venv from uv.lock
uv run alembic upgrade head
uv run uvicorn app.main:app --reload       # API
uv run python -m app.worker                # worker (separate terminal)
```

## Development

Install the pre-commit hooks once per clone:

```bash
uv run pre-commit install
```

On every commit they run ruff format, ruff lint, mypy, and a `detect-secrets` scan. CI (`.github/workflows/ci.yml`) runs the same checks plus the migrations and the test suite on every push and pull request.

Run the checks by hand:

```bash
uv run ruff format .        # format
uv run ruff check .         # lint
uv run mypy                 # type check (strict)
uv run pytest               # tests — needs Postgres running
uv run pre-commit run --all-files
```

The health test talks to a **real** database on purpose — a mocked connection would assert nothing — so start Postgres before running the suite:

```bash
docker compose up -d postgres && uv run pytest
```

There is no seed data yet; seeding arrives with the directory in Phase 2.

### Database changes

All schema changes go through Alembic. Never hand-edit the database.

```bash
uv run alembic revision -m "add users table"   # then write the migration
uv run alembic upgrade head
uv run alembic downgrade -1
```

The migration URL comes from `DATABASE_URL` in the environment, never from `alembic.ini`.

### Adding a dependency

```bash
uv add fastapi-users          # runtime
uv add --dev pytest-asyncio   # dev only
```

Commit the resulting `uv.lock`. CI installs with `--locked` and fails if the lockfile is stale.

## Configuration

Every variable the app reads is documented in [`.env.example`](.env.example) with dummy values. `.env` is gitignored and must never be committed — **no secrets in this repo, ever** (it is public).

Deliberate dummy credentials carry an inline `# pragma: allowlist secret` comment so the secret scan stays quiet about them. Regenerate the baseline only when you understand why it changed:

```bash
uv run detect-secrets scan --exclude-files '^\.venv/' --exclude-files '^\.git/' --exclude-files '^uv\.lock$' > .secrets.baseline
```

## Where things are

| Concern | File |
|---|---|
| Settings / env parsing | `app/config.py` |
| Engine, session factory, `get_session` dependency | `app/db.py` |
| App factory + lifespan | `app/main.py` |
| `GET /health` route | `app/routers/health.py` |
| Health logic (the `SELECT 1`) | `app/services/health.py` |
| Worker loop | `app/worker/main.py` |
| pgvector baseline migration | `migrations/versions/0001_enable_pgvector.py` |
