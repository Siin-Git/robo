# Disaster Recovery

## Neon DB loss → rebuild

1. Create a fresh Neon database (new connection string).
2. `export DATABASE_URL='…'` and run `alembic upgrade head`
   (0001→0003, additive only — no destructive migration exists).
3. Restore the latest weekly `pg_dump` artifact (GitHub Actions → backup
   workflow, 14-day retention):
   `pg_restore --dbname="$DATABASE_URL" robo_backup.dump`
4. Re-run parity + financial checks:
   `python scripts/verify_db_parity.py --source <last-known-good-sqlite>`
   (for pre-cutover operation the SQLite file itself is the primary and is
   copied to `data/archive/` with sha256 before any risky operation).
5. Point the app at the new URL (`DATABASE_URL` secret / Render env) and
   confirm `python -m src.db.status` + `/ready`.

## SQLite primary recovery (current operational mode)

- Every archive under `data/archive/` carries `{db, json}` with sha256.
- Restore = copy the archive file back to `data/forward_test.db`, then
  `APP_PROFILE=live python -m src.forward.preflight`.

## Rollback: PostgreSQL → SQLite

Cutover has NOT happened (no flag exists). If a future cutover misbehaves:

- Point `DATABASE_BACKEND=sqlite` back at the archived SQLite file.
  Safe **only if** no forward data (trades/NAV/views) was created on
  PostgreSQL after cutover — the preflight `Existing live history` line and
  the `scheduled_jobs` table show where writes happened.
- If PostgreSQL accepted live writes, automatic rollback is FORBIDDEN
  (data loss); reconcile with `verify_db_parity.py` in the PG→SQLite
  direction first (script supports arbitrary `--source`/`--dest`).

## What is backed up

- Weekly `pg_dump` custom-format artifact (database-level, 14 days).
- Pre-operation SQLite archives with sha256 (`data/archive/`).
- Schema always recoverable from `migrations/` (`alembic upgrade head`).
