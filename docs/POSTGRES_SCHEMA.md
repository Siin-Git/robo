# PostgreSQL Schema (Phase 3A mirror of the reverse-engineered SQLite)

`docs/CURRENT_SQLITE_SCHEMA.md` is the source of truth for what exists.
This document describes how it maps to PostgreSQL. DDL source of truth:
`migrations/versions/0001_initial.py` (render with
`DATABASE_URL=postgresql+psycopg://… alembic upgrade head --sql`).

## Relationship map (textual ER)

```text
participants 1──* accounts 1──* orders 1──* trades
     │               │──* portfolio_targets / holdings_daily / nav_daily /
     │                    performance_daily / events
     ├──* views *── themes
     └──* events
```

All FKs `ON DELETE RESTRICT`; no `CASCADE` anywhere. SQLite declares no FKs;
they are enforced starting at the PostgreSQL layer (and in tests via
`PRAGMA foreign_keys=ON`).

## Conventions

- IDs: existing string IDs preserved verbatim (`P001`, `A-SHADOW-…`,
  `E000001`, …). No UUID conversion.
- Timestamps: `TIMESTAMPTZ` for instant semantics (`created_at`,
  `updated_at`, `submitted_at`, `end_at`, event `timestamp`); `DATE` for
  calendar-day semantics (`join_date`, `effective_at`, `cycle_*`,
  `execution_at`, daily `date`, `valid_from/to`, `inception_date`).
  Stored convention: instants are UTC ISO (`+00:00`); date-only fields are
  bare `YYYY-MM-DD`.
- Money/quantity: `NUMERIC` (`quantity` 28,10; `price` 24,8; `market_value`
  24,4; `nav` 24,8; `weight` 18,12; costs 24,8). Sub-quantum differences
  vs SQLite REAL are covered by per-column parity tolerances (10× quantum).
- Payloads: `JSONB` (`weights_json`, `metrics_json`, event/model
  `payload_json`). Semantic (key-order-insensitive) parity.
- Statuses: `VARCHAR + CHECK` (no ENUM): participant active/inactive, order
  side/status, view status, nav_status, account/theme types.
- Flags: `BOOLEAN` (`themes.active`, `nav_daily.stale_price_flag`;
  SQLite stores 0/1).
- Append-only: `trades`, `events`, `nav_daily`, `holdings_daily`,
  `performance_daily` — repositories expose insert+read only.
- `portfolio_targets` stays header+JSON (faithful to source; no per-asset rows).
- `themes` keeps the inline ticker (no `theme_mappings` table exists in source).
- Operational tables (`counters`, `forward_state`, `prices_daily`) migrate as-is.

## Indexes

Status/type lookups (`participants.status`, `accounts(participant_id)`,
`accounts(account_type)`), view/participant/effective queries, order
account+status/effective, trade account+execution, holdings/nav account+date,
event timestamp/type/participant/account, targets account+effective.

## Backend portability note

`src/db/base.py` declares `TIMESTAMPTZ`/`JSONB` with SQLite variants
(`DateTime(timezone=True)`/`JSON`) so the same models run on SQLite for
offline verification and tests. Production PostgreSQL always sees the native
types (verified via offline `--sql` render).
