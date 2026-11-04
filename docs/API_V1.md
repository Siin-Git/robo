# Robo Advisor API v1

> WARNING: Phase 3B API does not provide authentication or authorization.
> Do not expose this API publicly. Authentication will be implemented in
> Phase 3C.

Base URL: `/api/v1` (plus top-level `/health`, `/ready`, `/docs`, `/redoc`).
Contract snapshot: `outputs/api/openapi_v1.json`.

## Conventions

- Numbers: weights/returns are JSON numbers (floats converted from NUMERIC;
  money likewise — precision caveat documented per endpoint, not strings).
- Timestamps: ISO 8601 with offset, never stripped
  (e.g. `2026-09-13T22:15:00+09:00`).
- Pagination: `limit` (default 50, max 200) + `offset` on list endpoints;
  responses carry `items/total/limit/offset`.
- Sorting: fixed server-side order except rankings (`basis` whitelist:
  `active_return|cumulative|ir|mdd`).
- Errors: `{error: {code, message, details}, request_id}` + `X-Request-ID`
  header; request logging (method/path/status/duration, no payloads).
- Pre-launch behavior: performance → `INSUFFICIENT_HISTORY` (null metrics),
  forward status → `NOT STARTED`, empty histories → `[]`. Never 500.

## Endpoints

| Method | Path | Notes |
|---|---|---|
| GET | `/health` | liveness, no DB |
| GET | `/ready` | 200 ready / 503 with reasons |
| GET/POST | `/api/v1/participants` | list (status/limit/offset), create → `P001`… |
| GET | `/api/v1/participants/{id}` | 404 `PARTICIPANT_NOT_FOUND` |
| POST | `/api/v1/participants/{id}/deactivate` | soft-deactivate + audit |
| POST | `/api/v1/participants/{id}/reactivate` | |
| GET | `/api/v1/themes` | `active` (default true), `theme_type` filter |
| GET | `/api/v1/themes/{id}` | inactive retrievable (optical_networking) |
| GET | `/api/v1/participants/{id}/views` | history, status filter |
| GET | `/api/v1/participants/{id}/views/current` | max 2 active |
| POST | `/api/v1/participants/{id}/views` | `{theme_ids[≤2], reason}`; domain cutoff/schedule reused |
| POST | `/api/v1/participants/{id}/views/{vid}/close` | audit event preserved |
| GET | `/api/v1/participants/{id}/portfolio` | personalized + expected vol/TE (null when unevaluable) |
| GET | `/api/v1/portfolio/core` | frozen CORE_V0.3 (identical for all) |
| GET | `/api/v1/participants/{id}/portfolio/comparison` | core/personalized/active diff |
| GET | `/api/v1/participants/{id}/performance` | `?start=&end=`; INSUFFICIENT_HISTORY envelope |
| GET | `/api/v1/participants/{id}/performance/nav` | chart-ready NAV pairs |
| GET | `/api/v1/participants/{id}/performance/active` | daily(last 60)/weekly/cumulative |
| GET | `/api/v1/participants/{id}/performance/attribution` | core/active/costs/themes + residual |
| GET | `/api/v1/participants/{id}/performance/contributions` | `?period=1M|3M|6M|1Y|ALL`; cumulative contribution by persisted ledger asset + reconciliation |
| GET | `/api/v1/me/performance/contributions` | current user's cumulative asset contributions from recorded NAV/holdings/trades |
| GET | `/api/v1/participants/{id}/performance/ledger` | persisted snapshots, price status, orders and trades; optional `start/end` |
| GET | `/api/v1/me/performance/ledger` | current user's Backend 1 ledger contract (`ledger-read-v1`) |
| GET | `/api/v1/rankings` | `period=weekly`, `basis`, `comparison` |
| GET | `/api/v1/benchmarks` | CORE_V0.3 / Neutral / Equal Weight |
| GET | `/api/v1/benchmarks/performance` | `?benchmark_version=` shadow NAVs |
| GET | `/api/v1/system/status` | profile/backend/versions/4 dates/counts |
| GET | `/api/v1/version` | api + model versions |
| GET | `/api/v1/admin/orders/pending` | dev only, NO AUTH |
| GET | `/api/v1/admin/trades` | filters + pagination, dev only, NO AUTH |

## Lifecycle states

Views: `new/hold/closed/rejected` + derived `execution_status`
(`PENDING`/`EXECUTED`). Forward status: `NOT STARTED` until launch;
`first_execution` pending until first fill.

## Error codes

`PARTICIPANT_NOT_FOUND`, `PARTICIPANT_INACTIVE`, `THEME_NOT_FOUND`,
`THEME_INACTIVE`, `VIEW_LIMIT_EXCEEDED`, `DUPLICATE_THEME`, `VIEW_NOT_FOUND`,
`PORTFOLIO_NOT_READY`, `BENCHMARK_NOT_FOUND`, `INSUFFICIENT_HISTORY` (status,
not error), `INVALID_BASIS/PERIOD/COMPARISON`, `VALIDATION_ERROR`,
`DATABASE_ERROR`, `INTERNAL_ERROR` → HTTP 200/201/400/404/409/422/503.

## Run

```bash
uvicorn src.api.main:app --reload            # dev
uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```

Respects `APP_PROFILE` / `DATABASE_BACKEND` / `DATABASE_URL`; prints the
safety banner at startup. Existing `src.forward.*` CLIs are untouched.
