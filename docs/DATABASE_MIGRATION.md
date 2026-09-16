# Database Migration Guide (SQLite → PostgreSQL mirror)

Operational primary stays **SQLite** in Phase 3A. PostgreSQL is a parallel
mirror; no cutover flag exists.

## 0. Prerequisites

```bash
pip install -r requirements.txt        # sqlalchemy, alembic, psycopg, dotenv
docker compose up -d postgres          # or any PostgreSQL 16
createdb robo_advisor                  # if not created by compose
```

Configure (never commit secrets):

```bash
cp .env.example .env
# set DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/robo_advisor
```

## 1. Create schema

```bash
alembic upgrade head
```

Verify without a server (renders PostgreSQL DDL, no connection):

```bash
DATABASE_URL=postgresql+psycopg://u:p@localhost:5432/robo_advisor \
  alembic upgrade head --sql | head -50
```

Dev databases can be torn down with `alembic downgrade base`
(never run against live data).

## 2. Dry run (no writes)

```bash
python scripts/migrate_sqlite_to_postgres.py \
  --source data/forward_test.db --dry-run
```

Expected output lists per-table row counts, detected issues (orphan FKs fail
the run — fix source data, never auto-delete), and `Ready to migrate`.

## 3. Migrate

```bash
python scripts/migrate_sqlite_to_postgres.py \
  --source data/forward_test.db
```

Rules: destination must be empty (refuses otherwise; no `--force` in V0);
single transaction (failure leaves no partial data); IDs, timestamps and JSON
payloads preserved byte-for-byte semantically; source sha256 recorded before
and after to prove it was untouched. Report:
`outputs/database/migration_report.json`.

## 4. Verify parity (independent script)

```bash
python scripts/verify_db_parity.py \
  --source data/forward_test.db
```

Checks schema presence, row counts, full PK sets, all field values
(per-column numeric tolerances), FK orphans, financial aggregates
(latest NAV, trade/cost sums, holdings identity), canonical hashes.
Exit 0 + `PARITY: PASS` required. Report:
`outputs/database/parity_report.json`.

## 5. Status

```bash
python -m src.db.status
```

## 6. Operational primary

Still SQLite. Phase 3A adds no cutover mechanism on purpose.
