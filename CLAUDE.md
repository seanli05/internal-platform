# DSS Internal Platform

Login-walled internal platform for the Data Science Society: a searchable club photo archive (semantic + face search), a member directory, and an exec dashboard. Separate app from the public marketing site.

Full context and the phased build sequence: @docs/BUILD_PLAN.md

This file is the set of **durable constraints that hold across every phase**. Read it before making changes. It is guidance, not enforcement — the security rules below must also be backed by real mechanisms (gitignore, CI secret scanning, tests), not trusted to this file alone.

---

## Locked stack — do not substitute

- **Backend:** FastAPI (Python). Not Django, not Flask.
- **Frontend:** Next.js / React, deployed separately from the backend.
- **Database:** Postgres with the `pgvector` extension. This is the ONLY datastore — member records, CLIP vectors, and face vectors all live here. Do NOT add a separate vector database or Redis.
- **Auth:** Google OAuth. Any Google account is allowed to sign in.
- **ML worker:** a Python process sharing THIS codebase (same package, second entrypoint). Not a separate service in another language.
- **Semantic search:** CLIP embeddings. **Face embeddings:** InsightFace / ArcFace — never CLIP for faces.
- **Photo storage:** S3-compatible bucket (Cloudflare R2 or Supabase Storage). The app owns the bytes.

If a task seems to need a different tool, STOP and flag it rather than substituting.

## Architecture invariants

- **Permissions are two-tier, enforced in ONE place.** Rule: a user may access a row if it is their own OR they are exec. There is no middle tier. Implement as a single reusable dependency and reuse it on every protected endpoint. Never re-implement the check ad hoc.
- **Enforcement is backend, not frontend.** Hiding a UI element is not access control. Every protected route must reject unauthorized requests with 403 at the API, independent of the UI. When you add or touch a protected route, state where the backend enforces the rule.
- **Membership ≠ identity.** Anyone can log in → `status: pending`. An exec approves them → `approved`. Login never grants membership; approval does.
- **The worker never blocks a request.** Uploads return immediately and create `photos` with `processing_status = pending`. The worker embeds/detects asynchronously and updates status. Never run embedding or face detection inline in a request handler.
- **This app is the source of truth for member records.** It syncs OUTWARD to Airtable. It never treats Airtable as authoritative.
- **Face recognition is opt-out at the index level.** `allow_face_recognition = false` must pull a person out of the matching index, not merely hide their label. "Don't recognize me" ≠ "don't appear in photos."

## Security — non-negotiable (public repo)

- **Never commit secrets.** No credentials in code, ever. All secrets via env vars. `.env` is gitignored; `.env.example` documents every variable with dummy values.
- **No real member data in the repo.** Seed scripts generate FAKE users only. Never commit real names, photos, biometric vectors, database dumps, or fixtures built from real members.
- **Dev-only backdoors are gated by `DEV_MODE` and absent otherwise.** The impersonation / "act as user" mechanism must not exist when `DEV_MODE` is off. Never reachable in production.

## Database

- All schema changes go through **Alembic migrations**. Never hand-edit schema or instruct hand-editing the database. Commit migrations alongside the code that needs them.
- The only sanctioned direct-write is the bootstrap seed script, and it goes through the ORM.

## How to work in this repo

- **One phase at a time.** Build the current phase's vertical slice end-to-end. Do not begin the next phase until asked. Phases are defined in @docs/BUILD_PLAN.md.
- **"Done when" is the contract.** Each phase has an acceptance criterion; the phase is finished only when it demonstrably passes.
- **Prove plumbing before adding ML.** Photo upload/store/display must work before any embedding or face code is added.
- **Keep it boring and documented.** This project will be handed to a future student; favor standard, legible solutions over clever ones.

## Definition of done — self-check before reporting any task complete

A change is not finished until ALL of these hold:

- [ ] Formatted and linted clean (`ruff` for Python; ESLint + Prettier for the frontend).
- [ ] Type checks pass (`mypy` or `pyright`; TypeScript in `strict` mode).
- [ ] Tests for the new behavior exist and the full suite passes.
- [ ] If the schema changed, an Alembic migration is included.
- [ ] If a new env var was introduced, `.env.example` documents it.
- [ ] If commands, endpoints, or architecture changed, the README / relevant docs are updated in the SAME change.
- [ ] If a protected route was touched, the backend permission check is present — and state where it is.
- [ ] No secrets, no debug prints, no commented-out code, no unrelated churn.

## Code quality

- **Formatters and linters are mandatory, not optional.** Run them before finishing; leave zero violations. Python: `ruff` (format + lint). Frontend: ESLint + Prettier.
- **Type everything.** Type hints on all Python signatures; Pydantic models at every API boundary (request *and* response). TypeScript `strict` on the frontend.
- **Thin routes, logic in a service layer.** Route handlers validate input and delegate; business logic lives in testable service functions. This keeps the permission dependency and worker logic reusable and unit-testable.
- **Fail loud, never silent.** No bare `except`. Validate at the API boundary. In the worker, a failure sets `processing_status = failed` with a reason — never a swallowed exception that makes a photo vanish.
- **Follow existing patterns.** Before adding a new way to do something, check how it's already done and match it. One canonical approach per concern.

## Documentation upkeep — docs drift is a bug

Documentation is part of the change, not a follow-up:

- Update the **README** whenever setup steps, run commands, or architecture change — in the same commit that changes them.
- Update **`.env.example`** the moment a new environment variable is introduced. A missing var here is the most common "works on my machine" failure.
- Update **`CLAUDE.md`** only when a locked decision or convention genuinely changes — flag it, don't change it silently.
- Keep each phase's **"Done when"** in the build plan honest if scope shifts.

## Testing

- **Write tests with the feature, not later.** A phase isn't done until its behavior is covered.
- **Highest-value targets, never skipped:** the permission dependency (own → allowed, other's → 403, exec → allowed) and the async seam (upload → `pending` → worker processes → searchable).
- **Never weaken a test to make it pass.** If a test fails, fix the code or fix the test's *correctness* — never delete or loosen it just to go green.

## Commits & pull requests

- **Small, focused commits** with messages describing the change and the why.
- **One phase per PR**, description referencing the phase and its "Done when" criterion.
- Never commit secrets, generated files, debug output, or unrelated formatting churn.

## Automate the enforceable rules (set up in Phase 0)

This file is guidance, not a guarantee — back the mechanical rules with tooling so they hold even when the file is ignored:

- **Pre-commit hooks:** formatter, linter, type check, and a secret scan on every commit.
- **CI (GitHub Actions):** run lint + type check + tests on every PR; block merge on failure.
- Stand both up during Phase 0 so every later phase inherits the guardrails automatically.

## Bootstrapping the first exec

Promoting to exec is an exec-only action, so the first exec is seeded out of band: a user logs in normally (lands `pending`), then a seed script reads `INITIAL_EXEC_EMAILS` from env and promotes matching users to `approved` + `exec`. After that, execs promote everyone else through the UI. Never hardcode exec emails in source.

## Project layout (target)

```
app/            FastAPI application (routes, models, the permission dependency, services)
app/worker/     worker entrypoint — CLIP + InsightFace processing; shares app/ models
migrations/     Alembic migrations
scripts/        bootstrap exec (INITIAL_EXEC_EMAILS) + dev fake-data seeding
tests/          pytest — prioritize the permission check and the async worker seam
docker-compose.yml
.env.example
```
