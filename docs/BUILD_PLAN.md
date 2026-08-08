# DSS Internal Platform — Build Plan

A member-facing internal platform for the Data Science Society: a searchable club photo archive with AI-powered semantic and face search, a personalized member directory, and an exec dashboard for club operations. This document is the plan of record — it captures every architectural decision, the data model, and a phased, vertical-slice build sequence you can work off of directly and hand to Claude Code.

---

## 1. What we're building (and why it's not a clone)

A login-walled web app, separate from the public marketing site, that gives every DSS member a personalized account. Its wedge — the feature people open on their own — is a **club photo archive with AI search**: not just "find photos of me" but context-aware queries like *"show me the National Geographic project group."* That context query is only answerable because the app also owns the **member directory** (who's on which project), so the photo tool and the directory are one coherent system, not two features. On top of that sits a private **member dashboard** (own attendance, own strikes, resume upload) and an **exec dashboard** (manage everyone, run the resume booklet) — the per-user private state that Notion structurally cannot do.

The reason this isn't a redundant clone of ClubExpress / CampusGroups / Notion: none of those know *your* people and *your* projects, none integrate with your existing stack, and none do context-grounded photo search over your own archive. The novelty lives in the intersection of your directory and your photos.

---

## 2. Locked architecture

Every one of these was decided deliberately. They are the load-bearing walls; treat them as settled.

| Layer | Choice | Why |
|---|---|---|
| Frontend | **Next.js / React**, deployed separately, linked from the marketing site | Standard, portfolio-legible; Claude Code carries the JS load |
| Backend | **FastAPI** (Python) | API-first fits React; you're strongest in Python; async suits background work |
| Database | **Postgres + pgvector** | One store for member records, semantic vectors, and face vectors — no separate vector DB |
| Auth | **Google OAuth** (any account) | Everyone has Google; no passwords to store; Berkeley accounts transparently route through CalNet |
| Membership gate | **Pending → exec-approved** | Identity (login) is decoupled from membership (approval); alumni keep their accounts |
| Permissions | **Two tiers**: member sees own, exec sees all | One flag + one rule; nothing in between |
| ML worker | **Python worker sharing the backend codebase** | Same models/DB; runs as a second process off a job queue |
| Semantic search | **CLIP** embeddings | Pure-pixel search ("whiteboard," "people laughing") |
| Face search | **InsightFace / ArcFace** embeddings | Purpose-built for faces (CLIP is bad at faces); separate index from CLIP |
| Photo storage | **S3-style bucket** (Cloudflare R2 or Supabase Storage) | Cheap at club scale; app owns the bytes so it can run models on them |
| Source of truth | **This app owns the member directory**, syncs outward to Airtable | Kills the three-copies-drifting problem |
| Google Photos | **Optional downstream mirror** via `appendonly`, never the backbone | 2025 API changes killed reading pre-existing libraries; don't depend on it |

**System in one breath:** React frontend → FastAPI backend → Postgres+pgvector, with a Python worker sharing the codebase that pulls jobs off a queue to embed photos and detect/match faces, photos living in a bucket, Google login gating a pending→approved membership flow.

**Deployment shape — three small pieces to keep alive:**
1. The FastAPI web process (serves the API)
2. The Python worker process (processes photos) — *same code, different entrypoint*
3. Postgres+pgvector + the storage bucket (managed; Supabase covers both plus auth helpers)

At club scale (low thousands of photos/year, low hundreds of members) none of this needs a GPU, Redis, or a dedicated vector database. CLIP and InsightFace run fine on CPU; the job queue can start as a polled Postgres table.

---

## 3. Core data model

The schema is the part most expensive to change later, so it's worth getting the shape right up front. Below are the core tables. Vector columns use `pgvector`.

### Identity & membership

**`users`** — one row per person who has ever logged in.
- `id`, `google_sub` (stable Google identity), `email`, `display_name`
- `status`: `pending` | `approved` | `alumni` | `removed`
- `role`: `member` | `exec` (this is your whole permission axis)
- `profile_photo_key` (bucket reference — the enrollment seed)
- `allow_face_recognition` (bool, default true) — the **recognize-vs-appear opt-out**
- `joined_at`, `created_at`

**`committees`** — Academic Development, Social Good, Consulting/renamed, etc.
- `id`, `name`, `slug`

**`projects`** — the grounding for context search (e.g., "NatGeo project"). *This is what makes "show me the NatGeo group" possible.*
- `id`, `name`, `committee_id` (nullable), `active`

**`memberships`** — user ↔ committee, and user ↔ project (either two join tables or one polymorphic `affiliations` table).
- `user_id`, `committee_id` / `project_id`, `role_in_group` (nullable, e.g. lead)

### Photos & search

**`events`** — album/context grouping (a datathon, a social, the NatGeo kickoff).
- `id`, `name`, `date`, `committee_id` (nullable)

**`photos`**
- `id`, `storage_key`, `uploaded_by` (→ users), `event_id` (nullable)
- `processing_status`: `pending` | `processing` | `done` | `failed`
- `clip_embedding` (vector) — the semantic-search index
- `width`, `height`, `caption` (nullable), `created_at`

**`detected_faces`** — one row per face found in a photo.
- `id`, `photo_id`, `bbox` (the crop region)
- `face_embedding` (vector) — the ArcFace vector for *this* face instance
- `matched_user_id` (nullable → users), `match_confidence`, `confirmed` (bool)

**`person_references`** — the gallery of known face vectors per member (**many per person**, not one).
- `id`, `user_id`, `face_embedding` (vector)
- `source`: `profile_seed` | `confirmed_from_photo`
- `photo_id` (nullable, if derived from a confirmed match), `created_at`

> Why `person_references` is separate and multi-row: a single posed signup selfie is a weak match against candids. Every time the system confidently matches someone in a real photo *and a human confirms it*, you fold that face back in as a new reference. Matching quietly improves over the semester instead of being frozen at the signup photo.

### Dashboard / operations

**`meetings`** — attendance events (distinct from photo `events`, or unify with a `type` field).
- `id`, `title`, `date`, `committee_id` (nullable)

**`attendance`**
- `id`, `user_id`, `meeting_id`, `status` (`present` | `absent` | `excused`), `recorded_by`

**`strikes`**
- `id`, `user_id`, `reason`, `issued_by`, `issued_at`

**`resumes`** — visible only to owner + exec.
- `id`, `user_id`, `file_key`, `uploaded_at`

### Processing (start simple)

No separate queue system to begin with: the worker polls `photos WHERE processing_status = 'pending'`. Add a `processing_jobs` table or Celery only if/when you need retries, scheduling, or multiple job types.

---

## 4. The MVP cut

You've decided v1 ships everything (photo tool **and** dashboard) in one release. That's fine — but there's still a meaningful **MVP milestone** *inside* that build: the smallest slice that is genuinely useful and demoable. Hitting it early de-risks the whole project and gives you something to show members and exec before the full v1 is done.

**MVP = Phases 0–4 below:** auth working, membership gating, photos uploading and displaying, and **semantic (CLIP) search returning real results.** At that milestone a member can log in, browse the archive, and type "datathon whiteboard" and get hits. That's the magnet feature alive. Faces (Phase 5) and the exec dashboard (Phase 6) complete v1 on top of that proven spine.

---

## 5. Phased build — vertical slices

The governing principle: **build vertically, not bottom-up.** Don't build all the models, then all the auth, then all the API, then finally something visible. Each phase is a thin slice that runs end to end and produces something you can *see and test*. The riskiest, most novel piece (the ML pipeline) comes *after* the boring plumbing is proven, so you're never debugging auth and embeddings at the same time.

### Phase 0 — Foundations
*Goal: an empty app that runs, deploys, and talks to a database.*

- Repo + project scaffold: FastAPI app, a `worker/` entrypoint sharing the same package, dependency management (uv or Poetry).
- Postgres with the `pgvector` extension enabled; migrations tool (Alembic).
- Local dev via Docker Compose (api + worker + postgres); pick a deploy target (Railway, Render, or Fly are all fine at this scale).
- One `/health` endpoint returning 200. Frontend: a bare Next.js app that fetches it.

*Done when:* the empty app deploys and the frontend can reach the backend.

### Phase 1 — Auth spine
*Goal: real Google login, end to end, with one protected route.*

- `users` table (minimal: identity fields, `status`, `role`).
- Google OAuth flow (a library like Authlib on the backend). On first login, create a `users` row with `status = pending`.
- Session or JWT strategy; a `/me` endpoint returning the current user.
- One protected backend route that rejects unauthenticated requests.
- Frontend: "Sign in with Google" button, an authenticated shell, one protected page that greets the user by name.

*Done when:* you can log in with any Google account and land on a protected page. **This is the spine — everything hangs off it.**

### Phase 2 — Membership & permissions
*Goal: the pending→approved gate and the two-tier rule, plus the directory.*

- Approval flow: pending users see a "waiting for approval" state; exec sees a pending-users list and can approve (→ `approved`) or reject (→ `removed`).
- The permission primitive, written **once**: a dependency that resolves "is this the requesting user's own row, OR is the requester exec." Every protected endpoint reuses it.
- Seed the first exec accounts manually (a script or DB insert) so there's someone to approve others.
- Directory: `committees`, `projects`, `memberships`; a members-list view and a member-profile view.
- **Profile picture upload** — this is the face-enrollment seed, so it belongs here even though matching comes later. Store to the bucket, save `profile_photo_key`.

*Done when:* an exec can approve a pending member, members appear in a directory with committee/project affiliations, and everyone has a profile photo.

### Phase 3 — Photo plumbing (no ML yet)
*Goal: prove the upload→store→display pipe before adding any brains.*

- `photos` and `events` tables.
- Upload: single and **bulk** (this is the primary flow — members dump event albums). Files go to the bucket; each photo row is created with `processing_status = pending`.
- Gallery view: browse photos, grouped by event/album.
- Basic metadata: uploader, event, caption.
- Nothing processes the `pending` photos yet — that's deliberate. You're proving the plumbing in isolation.

*Done when:* a member can bulk-upload 100 photos into an event album and browse them. (If bulk upload of 400 photos works without timing out, your storage flow is correct — note it must not block on any per-photo processing.)

### Phase 4 — Semantic search + the worker  ← **MVP milestone**
*Goal: the first "magic" moment — type a description, get matching photos.*

- Stand up the **worker** as a second process against the same codebase and DB.
- Job intake: worker polls `photos WHERE processing_status = 'pending'`, claims a batch, sets `processing`.
- CLIP: embed each photo, write `clip_embedding`, set `done` (or `failed` with a reason).
- Search endpoint: embed the query text with CLIP, do a pgvector nearest-neighbor search over `photos.clip_embedding`, return ranked results.
- Frontend: a search box + results grid. Photos become searchable a minute or so after upload; surface `processing` state so it's not confusing.

*Done when:* "someone presenting at a datathon" returns the right photos. **This is the magnet feature alive — the MVP milestone.**

### Phase 5 — Faces
*Goal: person search and the context queries that justified the whole idea.*

- Enrollment: worker embeds each member's profile photo with InsightFace → a `profile_seed` row in `person_references`.
- Per-photo face pass: worker detects faces, embeds each, writes `detected_faces` rows.
- Matching: compare each detected face against `person_references`; set `matched_user_id` + `match_confidence`. Respect `allow_face_recognition` — **skip matching for anyone opted out, even though their face still physically appears in group photos.**
- Confirm loop: exec (or the tagged member) confirms a match → fold that face in as a `confirmed_from_photo` reference. Matching improves over time.
- **Context search falls out here for free:** "NatGeo project group" = resolve the project's members → find photos containing 2+ of their matched faces. This is the payoff query, and it works only because faces link to members link to projects.
- The opt-out UI: a clear "don't recognize me" toggle on the member's own profile that pulls their references out of the matching index.

*Done when:* "photos of Luis" works, "the NatGeo group" works, and an opted-out member is never auto-identified.

### Phase 6 — Exec dashboard
*Goal: the private per-user state Notion can't do. Deliberately last — least novel, most "just work."*

- Attendance: `meetings` + `attendance`; exec records attendance per meeting; members see **only their own** history.
- Strikes: `strikes`; exec issues/views for anyone; members see **only their own** count.
- Resume booklet: members upload a resume (owner + exec visible only); exec exports a compiled booklet from all uploads — the recurring exec chore this whole thing justifies.
- All of it reuses the single permission primitive from Phase 2. A permission bug here isn't cosmetic — it's a member seeing someone else's strikes — so lean on the one tested rule rather than re-checking ad hoc.

*Done when:* a member sees a private dashboard of their own attendance/strikes/resume, and exec can manage everyone and export the booklet.

### Phase 7 — Polish, mirror, launch
*Goal: production-readiness, integrations, and handoff.*

- Airtable sync: push directory records outward to the Airtable that powers the marketing site (this app is the source of truth; Airtable is downstream).
- Optional Google Photos mirror: `appendonly` bulk-push from the platform for members who want photos in the native app. Nice-to-have, not backbone.
- Branding: DSS colors (`#0C706E`, `#1D8C89`, `#8FB573`), logo, the polished member-facing feel.
- Onboarding: a first-run flow that walks new members through approval + profile photo + the opt-out choice.
- **Handoff docs** (see §8 — do not skip this).

---

## 6. Development workflow

The plan above says *what* to build; this section is *how to build it without things quietly going wrong.* The through-line: keep a running app at all times, make every environment reproducible, and prove each slice before widening. None of this is heavy process — it's the small set of habits that keep a solo-built app from becoming un-runnable the moment you step away from it.

### 6.1 Local environment — make it reproducible from day one

The target is: someone clones the repo and runs **one command** to get the whole system up. That "someone" is future-you after a month away, the member who inherits this, and Claude Code working on a slice. If setup lives only in your head, all three are blocked.

- **Docker Compose** running every piece together: the FastAPI api, the worker, Postgres+pgvector, and a local stand-in for the bucket (MinIO speaks the S3 API, or just point at the real bucket with a `dev/` prefix).
- One `docker compose up` brings the stack alive; the api hot-reloads on code changes.
- A short **README** written *as you go*, not at the end — the exact commands to run it, seed it, and test it.

*Check it's going well:* a fresh clone on a different machine (or a wiped Docker state) comes up clean with no undocumented manual steps.

### 6.2 Secrets & config

- **Never commit secrets** — the Google OAuth client secret, database credentials, bucket keys. These live in a gitignored `.env` locally and in your host's secret manager in production.
- Commit a **`.env.example`** listing every variable with dummy values. This is the documented contract for what the app needs to run — it's how anyone else (or Claude Code) knows what to set.
- Use **separate Google OAuth credentials** for dev and prod: dev redirects to `localhost`, prod to your real domain. Mixing them causes confusing redirect-mismatch errors.

### 6.3 Database discipline

Schema is the expensive-to-change layer, so treat it with care:

- **All schema changes go through Alembic migrations.** Never hand-edit the database to add a column. Migrations are reproducible, reversible, and committed alongside the code that needs them — so a fresh clone builds the exact schema, and a future maintainer can see how it evolved.
- The one sanctioned exception to "don't touch the DB by hand" is the bootstrap seed script below — and even that goes through the ORM, not raw table edits.

### 6.4 Bootstrapping the first exec

The chicken-and-egg: promoting someone to exec is an exec-only action, so at the start nobody can promote anybody. You break the loop with a seed script that bypasses the app's own rules — deliberately, because those rules are what's blocking you.

1. **Log in normally first** with your Google account. This creates your `users` row as `status: pending`, `role: member` — same as anyone.
2. **Run the seed script**, which reads `INITIAL_EXEC_EMAILS` (e.g. `you@berkeley.edu,coprez@berkeley.edu`) from env and promotes any matching users to `approved` + `exec`.
3. **Never touch the DB by hand again** — you're now exec and promote everyone else through the UI.

Making the exec list an **env var rather than a hardcoded email** matters: it's config, it's documented, and it's how the next president seeds themselves without editing code. The script is a bootstrap-only backdoor — safe because running it requires direct database access, which only the developer has.

### 6.5 Dev seed data — a cast covering every state

Write a script that populates a fresh database with fake users hitting **every permission branch you need to test**: one `pending` member, one `approved` member, one `exec`, one who's opted out of face recognition, plus a couple of events with sample photos. Now you never have to manually click through approval each time you reset the DB, and every code path has a body to exercise.

### 6.6 Testing permissions — the part most worth doing well

Your entire security model is one rule ("is this row yours, OR are you exec"), so testing is really about *poking that one rule from every angle.*

- **Impersonation, behind a `DEV_MODE` flag.** Build a dev-only way to "act as" another user without logging out — usually a header your frontend can set. You flip between exec and member views in seconds. **This must be physically absent when `DEV_MODE` is off** — an impersonation backdoor shipped to production is a catastrophic hole, so gate it so the code path can't even exist in the real deployment.
- **Two browsers side by side.** Your exec account in a normal window, a test member in incognito. You literally watch "exec sees everyone's strikes / member sees only their own" at the same time. Zero code, fastest sanity check for any given screen.
- **Test the API directly, not just the UI.** This is the one people skip and regret. Hit the endpoint straight through FastAPI's auto-generated docs at `/docs` (or curl/Postman) as a member, requesting someone else's data, and confirm it returns **403**. Frontend hiding a button is *UX*; the backend saying no is *security* — and if the endpoint still answers, anyone who knows the URL walks right in. Always confirm the wall that actually counts.

### 6.7 Automated tests — the high-value few

Not chasing coverage numbers — targeting the handful of things where a *silent* break is expensive:

- **The permission check**, asserted from every angle: member requesting own data → 200; member requesting another's → 403; exec requesting anyone's → 200. This is the test that catches a later refactor quietly exposing someone's strikes.
- **The async seam:** uploading a photo creates a `pending` row, the worker processes it, and it becomes searchable. This guards the one genuinely non-obvious piece of engineering in the whole app.

Write these once each phase's logic stabilizes, not before — but do write them, because permissions and the worker are exactly what a future change breaks without any visible error.

### 6.8 Observing the worker — the novel piece

The worker is the part that behaves differently from a normal request/response app, so make it observable:

- Run it locally alongside the api and **watch its logs** as photos flow through.
- Have a way to see processing state at a glance — counts of `pending` / `processing` / `done` / `failed`.
- **Failed photos must not vanish silently.** On failure, set `failed` with a reason and surface it, so a corrupt image or a model hiccup is visible and retryable rather than a photo that just never appears in search.
- Test with a **real bulk upload** (a few hundred photos) to confirm nothing blocks the request and the queue drains behind it. This is the check that proves the async architecture actually works.

### 6.9 Working with Claude Code

Since Claude Code is carrying much of the build, a few habits keep its output on-rails:

- **Hand it one slice at a time**, with that phase's *"Done when"* as the explicit acceptance criterion. Don't paste the whole plan and say "build it" — feed it Phase 0+1, review, then Phase 2, and so on.
- **Give it the locked decisions as hard constraints** (FastAPI not Django, the single permission rule, pending→approved, the opt-out semantics) so it doesn't wander into a different architecture mid-build.
- **Review against the criteria — especially permissions.** The specific thing to check every time: did it actually enforce the rule in the *backend*, or did it just not render a button? Ask it to show you the endpoint-level check.
- **Hold the vertical-slice discipline.** Make it finish and prove one end-to-end slice before widening, so you're never debugging four half-built layers at once.

### 6.10 Rhythm & regression guarding

- **Branch per phase**, meaningful commits — the plan's phases map naturally to milestones, which keeps history legible and rollbacks easy.
- **Deploy early** — get *something* deployed at Phase 1, not at the end. "Works on my laptop but not deployed" is a category of bug you want surfacing in week one, not launch week.
- **Re-run the previous phase's "Done when" after each new phase** — a thirty-second manual check that adding faces didn't break search, that the dashboard didn't break the directory. Cheap regression guard, catches the ugly surprises early.

---

## 7. Cross-cutting concerns

These span every phase; design them in rather than bolting on.

**Consent & face data.** Face recognition on members is biometric data. Make recognition **opt-in-spirited and easily reversible**: the `allow_face_recognition` flag must genuinely pull someone out of the matching index, not just hide a label. Distinguish "don't upload me" from "don't *recognize* me" — an opted-out person can still appear in a group photo; they just aren't auto-identified. Provide a takedown path for individual photos. This is cheap now and genuinely unpleasant to retrofit after someone's upset.

**Photo governance.** Decide who can upload, whether photos are reviewable before becoming searchable, and how takedowns work. These hang off the Phase 2 role model, so they mostly resolve for free once roles exist.

**Security posture.** This app guards face vectors and strike records — it's the sensitive one, which is exactly why it's a *separate* app from the public marketing site. Keep the public site out of this auth boundary entirely.

**Google OAuth verification.** Requesting Google scopes triggers a consent screen; sensitive scopes trigger a verification review. Two escape hatches: an unverified app works for a small user count behind a warning (fine for a club), and you chose to allow non-Berkeley accounts, so the Workspace-internal shortcut is off the table — plan on the standard consent screen. **These policies shift; confirm the current thresholds when you reach Phase 1/7 rather than trusting any fixed number.**

**Async correctness.** The one genuinely non-obvious engineering piece: bulk uploads must never block a request on per-photo ML. Upload returns immediately; the worker fills in embeddings later; the UI shows `processing` → `done`. Get this seam right in Phase 4 and the rest of the ML work is ordinary.

---

## 8. Continuity — design for handoff from day one

The single most common failure mode for a platform like this: it's built by one talented person, works beautifully, and rots the moment that person graduates. You will graduate. So this isn't optional polish — it's a first-class requirement:

- **Boring, standard stack** (already chosen — FastAPI/React/Postgres, nothing exotic) so a future member can actually pick it up.
- **A README that lets someone run it locally in one sitting**, written as you build, not at the end.
- **Seed/admin scripts** for the un-automatable bits (first exec, resets).
- **An owner before you leave.** Identify who inherits this and pull them in *during* the build, not after. A platform with no owner in two years is an impressive project with a two-year fuse.

---

## 9. What's explicitly *not* in v1

Guard against "add custom features wherever we see fit" — that's the fun part and the scope trap. Let real demand pull features in rather than pre-building them. Deliberately deferred: task reminders/automations, notifications, event RSVP, a public alumni network, granular per-committee permission tiers (your two-tier model is intentionally flat), and anything that isn't the photo tool, the directory, or the private dashboard. Ship the wedge, get real users, then let usage tell you what's next.

---

## 10. Quick reference — the build order

0. **Foundations** — empty app runs and deploys
1. **Auth spine** — Google login, one protected route
2. **Membership & permissions** — pending→approved, two-tier rule, directory, profile photos
3. **Photo plumbing** — upload/store/gallery, no ML
4. **Semantic search + worker** — CLIP, pgvector search ← **MVP milestone**
5. **Faces** — enrollment, matching, context search, opt-out
6. **Exec dashboard** — attendance, strikes, resume booklet
7. **Polish & launch** — Airtable sync, optional Photos mirror, branding, handoff

Build each slice end-to-end before widening. Prove plumbing before adding brains. Keep the ML novelty downstream of the boring, tested spine.
