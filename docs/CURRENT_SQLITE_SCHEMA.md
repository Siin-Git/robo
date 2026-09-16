# Current SQLite Schema (reverse-engineered, read-only inspection)

Source: `data/forward_test.db` (live, pre-launch). Inspected via
`PRAGMA table_info / foreign_key_list / index_list` — no guessing.

- SQLite version behavior: `TEXT` PKs, `REAL` numerics, `INTEGER` flags,
  ISO-8601 `TEXT` timestamps (event/audit stamps carry `+00:00`, i.e. UTC).
- **No FOREIGN KEYs declared** on any table. **No secondary indexes**
  (only PK autoindexes).
- There is **no `theme_mappings` table**: the ETF ticker lives inline on
  `themes` (with `valid_from/valid_to` + `universe_version` for versioning).
- `portfolio_targets` is header-style (`weights_json`), not one-row-per-asset.

## Tables (15)

### participants — 0 rows
| column | type | null | pk | role |
|---|---|---|---|---|
| participant_id | TEXT | no* | 1 | string ID (`P001`), preserved on migration |
| display_name | TEXT | NO | | |
| status | TEXT | NO | | `active`/`inactive` |
| join_date | TEXT | NO | | DATE `YYYY-MM-DD` |
| leave_date | TEXT | yes | | DATE or NULL |
| created_at | TEXT | NO | | TIMESTAMPTZ ISO (UTC) |
| updated_at | TEXT | NO | | TIMESTAMPTZ ISO (UTC) |

`*`PK implies NOT NULL in practice.

### accounts — 3 rows (3 shadow definitions, no participant accounts yet)
| column | type | null | pk | role |
|---|---|---|---|---|
| account_id | TEXT | no* | 1 | `A-…` / `A-SHADOW-…`, preserved |
| participant_id | TEXT | yes | | NULL for shadows; logical FK → participants |
| account_type | TEXT | NO | | `core`/`personal`/`shadow` |
| shadow_name | TEXT | yes | | `neutral_60_40`/`equal_weight`/`core_v03` |
| benchmark_version | TEXT | NO | | e.g. `CORE_V0.3` |
| inception_date | TEXT | NO | | DATE (account opened) |
| initial_capital_krw | REAL | NO | | e.g. 100000000.0 |
| status | TEXT | NO | | `active` |
| created_at | TEXT | NO | | TIMESTAMPTZ ISO (UTC) |

### themes — 10 rows (9 active + `optical_networking` inactive)
theme_id PK TEXT; display_name TEXT NN; theme_type TEXT NN
(`sector`/`subsector`/`theme`); ticker TEXT NULL; market TEXT NULL;
currency TEXT NULL; active INTEGER NN (0/1); valid_from/valid_to TEXT NULL;
universe_version TEXT NN (`THEME_UNIVERSE_V0.1`); inactive_reason TEXT NULL.

### views — 0 rows
view_id PK TEXT (`V001`); participant_id TEXT NN (logical FK);
theme_id TEXT NN (logical FK); status TEXT NN (`new`/`hold`/`closed`/`rejected`);
submitted_at TEXT NN (TIMESTAMPTZ ISO); effective_at TEXT NN (DATE);
end_at TEXT NULL (TIMESTAMPTZ ISO); reason TEXT NULL;
theme_universe_version TEXT NN; cycle_week TEXT NN (DATE Friday, legacy);
cycle_date TEXT NULL (DATE Friday, canonical).

### portfolio_targets — 3 rows
target_id PK TEXT (`G001`); account_id TEXT NN (logical FK);
effective_date TEXT NN (DATE); kind TEXT NN (`core`/`personal`/`shadow`);
weights_json TEXT NN (JSON object asset→weight, sums to 1);
core_version TEXT NN; theme_universe_version TEXT NN;
risk_model_version TEXT NN; created_at TEXT NN (TIMESTAMPTZ ISO).

### orders — 0 rows
order_id PK TEXT (`O001`); account_id TEXT NN; asset_id TEXT NN;
side TEXT NN (`buy`/`sell`); target_weight REAL NN; submitted_at TEXT NN
(TIMESTAMPTZ ISO); effective_at TEXT NN (DATE); status TEXT NN
(`pending`/`executed`/`cancelled`); created_at TEXT NN.

### trades — 0 rows (append-only)
trade_id PK TEXT (`T001`); order_id TEXT NN (logical FK); account_id TEXT NN;
asset_id TEXT NN; execution_at TEXT NN (DATE); execution_price REAL NN;
quantity REAL NN (signed); gross_value REAL NN; transaction_cost REAL NN;
net_value REAL NN (signed cash impact).

### holdings_daily — 0 rows
Composite PK (account_id TEXT, date TEXT, asset_id TEXT);
quantity/price/market_value/weight REAL NN.

### nav_daily — 0 rows (append-only)
Composite PK (account_id TEXT, date TEXT); nav REAL NN; nav_base100 REAL NN;
daily_return REAL NULL (NULL on first row); cumulative_return REAL NN;
cash_balance REAL NN; stale_price_flag INTEGER NN;
nav_status TEXT NN (`OK`/`STALE_PRICE`); benchmark_version /
theme_universe_version / risk_model_version / execution_rule_version TEXT NN.

### performance_daily — 0 rows
Composite PK (account_id, date); metrics_json TEXT NN (JSON metrics object).

### prices_daily — 39042 rows
Composite PK (asset_id TEXT, date TEXT); price REAL NN (KRW levels);
source TEXT NN (e.g. `snapshot+provider-bootstrap`, `live-refresh`).

### events — 10 rows (append-only)
event_id PK TEXT (`E000001`); event_type TEXT NN; participant_id TEXT NULL;
account_id TEXT NULL; timestamp TEXT NN — **column name is `timestamp`**,
TIMESTAMPTZ ISO (UTC); payload_json TEXT NN (JSON object);
model_version TEXT NN.

### model_versions — 3 rows
version_id PK TEXT; version_type TEXT NN (`benchmark`/`theme_universe`/`risk_model`);
version TEXT NN; created_at TEXT NN; payload_json TEXT NN (JSON).

### counters — 2 rows
name PK TEXT (`P`, `E`, …); value INTEGER NN. ID-generator state.

### forward_state — 0 rows
key PK TEXT (`forward_test_inception_at`, `first_execution_at`);
value TEXT NULL; updated_at TEXT NULL. NULL/absent = not started (valid state).

## Timestamp convention (verified from stored values)

- `*_at`, `created_at`, `updated_at`, `timestamp` (events): full ISO with
  `+00:00` → UTC. PostgreSQL mapping: `TIMESTAMPTZ`.
- `join_date`, `leave_date`, `inception_date`, `effective_at`, `cycle_*`,
  `execution_at`, `effective_date`, daily `date`, `valid_from/to`: bare
  `YYYY-MM-DD` → PostgreSQL `DATE`.

## Deltas vs the Phase 3A prompt's sketch (intentional, faithful to reality)

- No `theme_mappings` table (inline ticker on `themes`).
- `portfolio_targets` keeps header+JSON shape (no per-asset rows).
- `events.timestamp` (not `event_timestamp`); no `execution_at` on views
  (execution dates live on `trades`); no `created_at/updated_at` on views.
- `nav_daily` carries 4 version columns + `nav_base100`; `daily_return` NULLs.
- Extra operational tables migrated as-is: `counters`, `forward_state`,
  `prices_daily`, `performance_daily`.
