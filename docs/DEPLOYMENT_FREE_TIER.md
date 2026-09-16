# Free-Tier Deployment Guide (Vercel + Render + Neon + GitHub Actions)

Target: `$0/month` MVP. Operational primary stays **SQLite** until the
PostgreSQL cutover checklist passes (live PG server required — not yet
provisioned); everything below prepares that path without breaking SQLite.

## 1. Neon (PostgreSQL)

MANUAL STEP REQUIRED:
1. Create a free Neon project + database `robo_advisor`.
2. Copy the connection string (Neon requires SSL; keep `?sslmode=require`).
3. Locally: `export DATABASE_URL='postgresql+psycopg://…'`.
4. `alembic upgrade head` (creates 0001→0003).
5. `python scripts/migrate_sqlite_to_postgres.py --source data/forward_test.db --dry-run`
6. `python scripts/migrate_sqlite_to_postgres.py --source data/forward_test.db`
7. `python scripts/verify_db_parity.py --source data/forward_test.db` → `PARITY: PASS`.
8. Reports land in `outputs/database/`.

Cutover to `DATABASE_BACKEND=postgres` happens ONLY when every §8 parity item
passes. Until then the app keeps running on SQLite (no cutover flag exists).

## 2. Render (FastAPI)

MANUAL STEP REQUIRED: create a free Web Service from the repo.
`render.yaml` in the repo root declares the service mkdir:

- build: `pip install -r requirements.txt`
- start: `alembic upgrade head && uvicorn src.api.main:app --host 0.0.0.0 --port $PORT`
  (single instance only — never scale without moving migrations out of start)
- health check path: `/health` (never `/ready`, so DB blips can't restart-loop)
- env: `APP_PROFILE=live`, `DATABASE_BACKEND=postgres`, `DATABASE_URL` (secret),
  `ALLOW_PUBLIC_REGISTRATION=false`, `CORS_ALLOWED_ORIGINS=<Vercel URL>`,
  `AUTH_COOKIE_SECURE=true`, `PYTHON_VERSION=3.10.11`.

Verify: `GET /health` → 200; `GET /ready` → ready reasons if any;
login sets `HttpOnly; Secure; SameSite=Lax` cookies.

## 3. Vercel (Next.js)

MANUAL STEP REQUIRED: import `web/` as a Vercel project.
Env: `FASTAPI_INTERNAL_URL=<Render URL>` (server-side only, never
`NEXT_PUBLIC_*`), `NEXT_PUBLIC_APP_NAME`. The thin `/api/v1/*` proxy forwards
cookies per-cookie (split `Set-Cookie`, verified in Phase 3D E2E). CORS on the
API stays whitelist-only (no `*` with credentials, enforced by test).

## 4. GitHub Actions (scheduler + CI + backup)

MANUAL STEP REQUIRED: add repo secret `DATABASE_URL` (used when the PG
primary is live; until then jobs run against the operational SQLite checkout
— see limitation note below).
Workflows: `daily_forward.yml` (22:30 UTC = 07:30 KST), `weekly_views.yml`
(Fri 09:10 UTC = Fri 18:10 KST), `monthly_rebalance.yml` (1st 00:30 UTC),
`backup.yml` (weekly `pg_dump` → 14-day artifact), `ci.yml` (backend +
frontend tests/build). All jobs support `workflow_dispatch` with optional
`date` + `dry_run`. Concurrency group `forward-jobs` serializes runs.
Job registry (`scheduled_jobs` table): duplicate claims are skipped, stale
`running` rows reclaimed after 6h, failures recorded with non-zero exit.

LIMITATION (honest): the forward engine CLIs are SQLite-file oriented, so
until engine PostgreSQL support lands, scheduled production execution targets
the SQLite operational DB and Neon stays a verification mirror. The workflows,
idempotency, locking, and dry-run paths are backend-agnostic and go live with
the cutover unchanged.

## 5. Verification

```bash
python scripts/deployment_smoke_test.py   # FRONTEND_URL/BACKEND_URL/SMOKE_* env
APP_PROFILE=live python -m src.forward.preflight   # expect NOT STARTED / YES
python -m src.db.status
```

Phase 3F (not 3E) registers real participants and runs the explicit launch.
3E never auto-launches.
