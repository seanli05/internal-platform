# Database migrations (Alembic)

The schema is defined in `app/models.py`, but the database only changes when a
**migration** runs. The app never creates or alters tables itself.

## The three pieces

| Piece | Where | What it is |
| --- | --- | --- |
| Migration scripts | `migrations/versions/*.py` | One file per schema change, with `upgrade()` and `downgrade()`. Each names its parent in `down_revision`, forming a chain. |
| Version table | `alembic_version` in the DB | One row: the ID of the last migration applied to *this* database. |
| Wiring | `migrations/env.py` | Connects Alembic to `DATABASE_URL` (from `app/db.py`) and to `Base.metadata` (from `app/models.py`). |

`alembic upgrade head` reads `alembic_version`, then runs every script after it
in the chain. Any database, at any version, ends up at the same schema.

## Changing the schema (the everyday loop)

```bash
alembic upgrade head                                   # 1. DB must be current first
# 2. edit app/models.py
alembic revision --autogenerate -m "add user role"     # 3. writes a DRAFT script
# 4. READ the new file in migrations/versions/ (checklist below)
alembic upgrade head                                   # 5. apply it to photos.db
uv run pytest                                          # 6. includes the drift check
# 7. commit the models.py change AND the migration together
```

Autogenerate diffs your models against **the live database**, not against
old scripts. That's why step 1 matters: on an outdated DB it would re-generate
changes that already have a migration.

## Review checklist for every generated script

- [ ] **New NOT NULL column on a table with rows?** It needs a
  `server_default=` (or a data step), or the upgrade fails: existing rows
  would have no value.
- [ ] **A rename?** Autogenerate sees `drop_column` + `add_column`, which
  **deletes the data**. Replace with `batch_op.alter_column("old", new_column_name="new")`.
- [ ] **Existing rows need a value set?** e.g. mark current users approved.
  Add an `op.execute("UPDATE ...")` after the column is added.
- [ ] **`downgrade()` really reverses `upgrade()`?** Read it; don't assume.
- [ ] **Nothing unexpected?** A `drop_table` you didn't intend usually means a
  model wasn't imported.

See the SQL before running it: `alembic upgrade head --sql`.

## Commands

| Command | Does |
| --- | --- |
| `alembic upgrade head` | Apply every pending migration. |
| `alembic current` | Which revision this DB is at. |
| `alembic history` | The whole chain. |
| `alembic check` | Fail if models.py has changes no migration covers. |
| `alembic downgrade -1` | Undo the last migration. (`head` is a destination, so `downgrade head` does nothing.) |
| `alembic downgrade base` | Undo everything (empty schema). |
| `alembic -x db_url=sqlite:///./scratch.db <cmd>` | Run any command against another DB, e.g. a copy, instead of photos.db. |

## Rules

1. **Never edit a migration after it has run anywhere but your laptop**
   (a teammate's DB, production). Those DBs already record it as done, so the
   edit never runs there and the schemas silently diverge. Write a new
   migration instead. Before that point, `downgrade -1` → delete → regenerate
   is fine.
2. **The app never changes the schema.** No `create_all` in app code. Tests
   are the exception: they use `create_all` on throwaway DBs, and
   `tests/test_migrations.py` proves the scripts produce the same schema.
3. **Commit the model change and its migration together.**
4. **Try risky migrations on a copy first:**
   `cp photos.db scratch.db && alembic -x db_url=sqlite:///./scratch.db upgrade head`

## Troubleshooting

| Error | Meaning |
| --- | --- |
| `no such table: users` when the app runs | Fresh DB, migrations not applied. Run `alembic upgrade head`. |
| `Target database is not up to date` | You ran autogenerate on a DB that's behind. `alembic upgrade head` first. |
| `Can't locate revision identified by '…'` | The DB's `alembic_version` names a script that isn't in `migrations/versions/` (deleted, or on another branch). |
| `test_migrations_match_models` fails | You changed models.py without a migration. Run autogenerate. |

## Moving to Postgres later

Change `DATABASE_URL` in `app/db.py`, then `alembic upgrade head` builds the
whole schema in an empty Postgres DB from the same scripts (`render_as_batch`
is harmless there). Alembic moves the **schema only**; copying existing rows
from SQLite is a separate one-time job, and Postgres will reject rows SQLite
let slide (wrong types, foreign keys pointing at deleted rows).
