---
name: db-migrations
description: Manage DSS database schema changes with Alembic — add/alter/remove columns or tables, create or review a migration, upgrade/downgrade the database, check current version or drift. Use whenever app/models.py changes or the user asks about the DB schema or migrations.
---

# DSS database migrations

Human reference: `docs/migrations.md`. Follow its rules; this file is the procedure.

This is a learning project: explain each step and what the generated script
does, don't just run commands. The user runs the app server themselves.

## Ground rules

- **`photos.db` is the user's data.** Any command that changes it
  (`upgrade`, `downgrade`, `stamp`) needs the user's go-ahead in this turn.
  Read-only commands (`current`, `history`, `check`, `--sql`) are fine.
- Rehearse on a copy in the scratchpad, never in the repo:
  `alembic -x db_url=sqlite:///<scratchpad>/rehearsal.db ...`
- **Never edit a migration that is committed**, unless the user confirms it
  has only ever run on their machine. Otherwise write a new migration.
- Never add `create_all` to app code. Tests may use it.
- Use `.venv/bin/alembic` (or `uv run alembic`) from the repo root.

## Procedure: schema change

1. **Preflight.** `alembic current` and `alembic heads` should match. If the DB
   is behind, ask before `alembic upgrade head`; autogenerate against a stale
   DB re-generates old changes.
2. **Edit `app/models.py`.** Group the related changes of one feature into one
   migration.
3. **Generate:** `alembic revision --autogenerate -m "<short what>"`.
4. **Review the new script** against the checklist in `docs/migrations.md`
   (NOT NULL needs `server_default`; renames show up as drop + add and lose data;
   data backfills; `downgrade()` reverses `upgrade()`; no surprise drops).
   Fix it, then walk the user through it line by line.
5. **Rehearse:** copy `photos.db` to the scratchpad, then run
   `upgrade head`, `downgrade -1` and `upgrade head` against the copy.
   This proves the script works on real existing rows, not just an empty DB.
6. **Test:** `.venv/bin/python -m pytest tests/test_migrations.py`. It runs no
   HTTP. The full suite includes API tests; hand that command to the user.
7. **Apply to `photos.db`:** only with the user's OK, using `alembic upgrade head`.
8. Offer to commit `models.py` and the migration together.

## Procedure: undo

- Bad migration that has only run locally: `downgrade -1` (with the user's OK),
  delete the script, fix the models, then regenerate.
- Already committed or shared: write a new migration that reverses it.

## Diagnose

Match errors against the troubleshooting table in `docs/migrations.md`.
