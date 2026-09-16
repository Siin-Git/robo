# Personalized Robo Advisor Prototype

위험 수준에 맞는 기본 자산배분을 고른 뒤, 관심 테마를 주식 비중 안에서 반영하고 모의운용 성과와 자산별 기여도를 확인하는 웹 프로토타입입니다. 실제 주문이나 투자 권유를 수행하지 않습니다.

## 개발팀 인수인계 시작점

처음 받는 개발팀은 아래 순서로 확인하세요.

1. [제품 흐름과 화면 의도](docs/PRODUCT_GUIDE.md)
2. [기술 구조와 실행 방법](docs/TECHNICAL_HANDOFF.md)
3. [구현 상태와 다음 작업](docs/STATUS_AND_NEXT_STEPS.md)
4. [GitHub 전달 체크리스트](docs/GITHUB_HANDOFF_CHECKLIST.md)

### 로컬에서 가장 빠르게 실행

필수 환경은 Python 3.10 이상과 Node.js 20.19 이상 또는 22.12 이상입니다.

```powershell
git clone https://github.com/Siin-Git/robo.git robo-advisor
cd robo-advisor

Copy-Item .env.local.example .env.local
Copy-Item web\.env.example web\.env.local

python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
cd web
npm ci
cd ..
.\.venv\Scripts\python.exe scripts\start_local.py
```

예시 환경변수에는 개인 키나 운영 비밀번호가 없습니다. 로컬 미리보기 계정은
`localtest@example.com` / `robo-local-2026`이며 각 개발자의 로컬 SQLite에서만
사용하세요. `.env.local` 파일은 Git에 포함되지 않습니다.

Windows에서는 `scripts\start_local.ps1`을 실행해도 됩니다. 로컬 DB가 없으면 초기화를 안내하고, 백엔드 `http://127.0.0.1:8000`과 프론트엔드 `http://localhost:3000`을 시작합니다. 비밀번호나 실제 DB 파일은 저장소에 포함하지 않습니다.

### 현재 제품 범위

- 위험 수준 선택: Efficient Frontier와 자산별 기대수익률·변동성 확인
- 관심 테마 선택: 카테고리별 최대 2개, 총 테마 비중 최대 15%
- 최종 확인: 기본 포트폴리오와 개인화 포트폴리오 비교
- 내 포트폴리오: 자산 구성, 테마 비중, 위험 변화 확인
- 투자 현황: 모의운용 수익률, CORE 벤치마크, 낙폭, 자산별 기여도
- 인증·권한: 사용자/관리자 역할과 서버 세션

> 이 프로토타입은 연구·모의운용용입니다. 기대수익률은 장기 가정이며 예측치가 아닙니다. 실제 투자, 주문 전송, 세금·실거래 비용 처리는 제공하지 않습니다.

---

## 금융 엔진 개발 기록

아래 내용은 모델 재현과 과거 개발 결정을 위한 상세 기술 기록입니다.

## Core Benchmark Engine V0.3 (FROZEN)

KRW-based strategic benchmark for a future personalized robo-advisor.
Phase 1.6 stabilizes expected returns with Black-Litterman (Neutral-implied
prior + 25%-confidence external CMA views) and freezes **Core Benchmark V0.3**.
Phase 1.5 (`CORE_V0.2`, direct CMA) and Phase 1 (`CORE_V0.1`, Max-Sharpe)
results are preserved under `outputs/` for comparison.

## 1. What this is

- 9 risky assets + KRW cash (cash is a 0–20% optimizer variable in V0.2)
- KRW-denominated returns; IEF/TIP use a simplified KRW-hedged proxy (local USD return, no FX leg)
- Strategic expected returns used **directly** (no realized-vol geo→arith conversion in the benchmark path)
- 5Y weekly Ledoit-Wolf primary risk model (3Y sensitivity)
- Core Benchmark V0.3 = BL-posterior max expected return s.t. vol ≤ Neutral 60/40 vol
- V0.2 (direct CMA) preserved for comparison; Tangency/Max-Sharpe diagnostic only

## 1b. Why V0.3 (BL stabilization)

V0.2 put external CMA point estimates straight into the optimizer: 3 assets hit
upper bounds, a +0.5pp UST shock moved its weight +18.6pp, and 3Y/5Y weights
differed by L1 0.38. V0.3 instead centers on the Neutral-implied equilibrium
prior (`π = δΣw`, `δ = (E_neutral − rf)/σ²`) and blends CMA views at 25%
confidence (`τ = 0.05`, Idzorek-style diagonal Omega, solve-based, no `inv`).
Result on the frozen snapshot: 0 cap hits, max shock move 6.6pp (median −32%),
horizon L1 0.14, neutral ER uplift +17bp at identical risk. Operating band
10–50% confidence is smooth; full-trust (c→100%) shows corner multiplicity and
is not used. See `bl_methodology.json` and `benchmark_decision_metrics.json`.

## 2. Scope (Phase 1.5)

Methodology validation + freeze only. No Black-Litterman, sector/theme ETFs,
personalization, login, UI, DB, ML, momentum, regimes, single stocks, costs,
auto-rebalance, or forward NAV tracking.

## 3. Asset universe

| asset_id | proxy | FX treatment |
|---|---|---|
| us_equity | VTI | unhedged |
| developed_ex_us | IEFA (was VEA; MSCI EAFE excludes Korea by construction) | unhedged |
| emerging_markets | VWO (FTSE EM excludes Korea by construction) | unhedged |
| korea_equity | 069500.KS | KRW native |
| us_treasury | IEF (hedged proxy) | hedged (local USD) |
| korea_treasury | 114260.KS | KRW native |
| tips | TIP (hedged proxy) | hedged (local USD) |
| gold | IAU | unhedged |
| global_reit | REET | unhedged |
| cash | KRW risk-free, ER 3%, vol 0 | — |

FX: `KRW=X`. The hedged proxy is simplified (no hedge carry/cost); see
`methodology_changes.json`.

## 4. Expected return

`config/expected_returns_v0.yaml` — strategic nominal long-term assumptions
(US 6.3%, Dev 6.0%, EM 7.2%, Korea 6.8%, UST 4.9%, KT 4.2%, TIPS 4.9%,
gold 5.5%, REIT 6.7%, cash 3.0%), used directly as optimizer inputs
(`expected_return_convention = strategic_nominal_long_term_assumption`).
`geometric_to_arithmetic` is retained for diagnostics only.

## 5. Risk model

- Primary: 5Y weekly Ledoit-Wolf (`sklearn` when installed, else internal
  pure-numpy implementation), annualized ×52
- Sensitivity: 3Y weekly Ledoit-Wolf (same method)
- Neutral 60/40 reference vol (cash vol 0) = `target_volatility`

## 6. Benchmark definition

Maximize `w'μ` s.t. `vol(w) ≤ target_vol`, `sum(w)=1`, `w ≥ 0`, per-asset caps
(§9 of the Phase 1.5 spec), equity ≤ 70%, gold+REIT ≤ 20%, cash ≤ 20%.
Solved by bisection on the risk-aversion of `min -m'w + γw'Cw`.
Tangency is diagnostic (`PRIMARY BENCHMARK = FALSE`).

## 7. How to run

```bash
cd robo-advisor
pip install -r requirements.txt
python -m src.pipeline.run_core_v0 --data-mode live      # fetch + freeze snapshot
python -m src.pipeline.run_core_v0 --data-mode snapshot  # reproduce without network
python scripts/cross_validate_standard_lib.py            # sklearn/scipy check (NOT RUN here)
python -m pytest tests -q
```

Console prints data period, ER convention, neutral anchor, weights, expected
return/vol/Sharpe, horizon L1, bound diagnostics, and `STATUS: PASS / FAIL`.

## 8. Outputs (`outputs/latest/`)

`asset_summary.csv`, `expected_returns.csv`, `weekly_returns_krw.csv`,
`covariance_5y_primary.csv`, `covariance_3y_sensitivity.csv` (+ legacy
`covariance_3y.csv`), `correlation_5y_primary.csv`,
`correlation_3y_sensitivity.csv`, `efficient_frontier.csv`,
`core_benchmark_weights.csv` + `core_benchmark_v02_weights.csv`,
`neutral_60_40_weights.csv`, `neutral_60_40_risk.json`, `tangency_weights.csv`,
`comparator_weights.csv`, `risk_horizon_sensitivity.csv`,
`expected_return_sensitivity.csv`, `bound_hit_diagnostics.csv`,
`benchmark_comparison.csv`, `methodology_changes.json`, `run_metadata.json`,
`cross_validation.json`, plus PNGs (`frontier_v02`, `weights_compare`,
`horizon_3y5y`, `er_sensitivity`, `nav_comparison`, correlations).

Frozen input snapshot: `data/snapshots/SNAPSHOT_20260911_V0/`
(hex-float CSVs, bitwise reproducible).

## 9. Known warnings (V0.2 run, 2026-09-12)

- 3 assets at upper bound (EM/Korea/REIT at cap) → concentration warning
- korea_treasury 0%, cash 0% (1 risky zero weight: ok)
- 5Y-vs-3Y weight L1 = 0.38 (same skeleton: EM/Korea/REIT caps, KT zero)
- ER +0.5pp: largest own-weight responses us_treasury +18.6pp, us_equity +11.6pp;
  no 0↔cap flips

## 10. Limitations

- Expected returns are strategic assumptions, not forecasts
- Simplified hedged proxy (no hedge carry/costs)
- No transaction costs/taxes; historical diagnostic is static-weight,
  **NOT A WALK-FORWARD BACKTEST**
- Free Yahoo data quirks; not investment advice

---

# Phase 2: Forward Test / Paper Trading V0

## 1. Purpose

Track frozen **CORE_V0.3** against live market prices, let a dynamic set of
participants submit weekly sector/theme views, build capped active sleeves on
top of the same core, and accumulate Core-vs-Personalized NAV, risk and
attribution for the weekly briefing. Research on the benchmark itself is over;
this is the operating system.

## 2. Frozen benchmark

`outputs/frozen/CORE_V0.3/` (`weights.json`, `metadata.json`, optimizer config
copy) is written once by `init_forward_test` from Phase 1.6 outputs and never
overwritten. Upgrades create new versions tracked as shadows; history is never
rewritten.

## 3. Participants (dynamic N)

SQLite `data/forward_test.db`; `add` / `deactivate` / `reactivate` / `list`
via `python -m src.forward.participants`. Soft-deactivation, per-participant
inception dates, no hardcoded headcount. Inactive participants cannot submit.

## 4. Weekly views

Max 2 active themes, positive-only, default `hold_existing`, explicit `close`.
Cutoff Friday 18:00 Asia/Seoul; late submissions join the next cycle.
`submitted_at` / `effective_at` / execution dates are strictly separated —
execution only uses closes on/after the effective session (next available
close per asset calendar). No retroactive fills.

## 5. Active sleeve

Budget 15% total / 10% single / default 10% (1 theme) or 7.5%+7.5% (2 themes),
funded **only from the equity sleeve** (proportional; region-map hook kept),
guardrail `personal vol ≤ core vol + 1.0pp` with proportional downscaling.
TE always stored (5Y Ledoit-Wolf convention, monthly refresh).

## 6. Accounts & NAV

Core + Personalized paper accounts per participant, plus system shadows
(`neutral_60_40`, `equal_weight`, `core_v03`). Fractional shares, 5bps trading
cost deducted from cash, KRW accounting, NAV base 100, daily holdings snapshots,
stale/missing-price flags (14-day lookback, no unbounded fills).

## 7. Operations

```bash
python -m src.forward.init_forward_test
python -m src.forward.participants add --name "User A" --join-date YYYY-MM-DD
python -m src.forward.views submit --participant P001 --theme ai --reason "..."
python -m src.forward.run_daily      # refresh, execute, value, guardrails
python -m src.forward.run_weekly     # cutoff batch, active targets + orders
python -m src.forward.run_monthly    # risk refresh + core rebalance
python -m src.forward.generate_briefing
python -m src.forward.seed_demo      # 3 demo participants, explicit only
```

Outputs: `outputs/forward/latest/` (NAVs, performance, rankings incl.
common-period active return, views, weights, attribution, pending orders,
`system_status.json`, `dashboard.html`), `outputs/forward/weekly/YYYY-MM-DD/`,
plots (core-vs-shadow, participant NAVs, ranking, drawdown).
`scripts/replay_validation.py` replays the full loop on synthetic history
(265 trades in the reference run) into `outputs/forward/validation/`.

## 8. Current live status (2026-09-13, Phase 2.1 clean launch)

Live DB reinitialized from zero after archiving the demo-contaminated
prelaunch DB (`data/archive/` + sha256). 0 participants, 0 views/orders/trades;
shadow targets recorded, first execution pending next available prices.
Saturday demo submissions now resolve to cycle 2026-09-18 / effective
2026-09-21 (single canonical resolver). Performance starts only after first
execution — never backfilled. Preflight: READY TO LAUNCH: YES.

## 9. Limitations

Paper trading only (no brokerage, no real money); single-ETF theme proxies
(`optical_networking` registered inactive — no suitable ETF); no leverage/
short/options; no BL user-view integration; static HTML dashboard (no
Streamlit dependency); monthly risk refresh; Korea/US holidays inferred from
price availability.

---

# Phase 2.1: Launch Hardening

## 1. View dates (single source of truth)

`resolve_view_schedule()` in `src/forward/views.py` computes
`cycle_date` + `effective_at` once at submission; every other module reads the
DB values. Friday ≤18:00 KST → same-Friday cycle, effective next weekday.
After cutoff / weekends → next-Friday cycle, effective Monday after it.
Asset-level `execution_at` comes from price availability per asset
(holidays shift execution, never the view itself).

## 2. Profiles

`APP_PROFILE=live|demo|validation` → `data/forward_test.db` /
`data/forward_demo.db` / `data/forward_validation.db` via
`src/forward/runtime.py` (the only place that maps profile→path). Every CLI
prints the safety banner. `seed_demo` refuses LIVE; the replay touches only
the validation DB (hash-verified by test).

## 3. Dates

`benchmark_model_date` (V0.3 freeze) vs `benchmark_snapshot_date` (data end)
vs `forward_test_inception_date` (inception event) vs `first_execution_date`
(first trade; NAV=100 anchors only after it). All four are in
`system_status.json` and the dashboard. No retroactive fills, no pre-execution
NAV rows.

## 4. Launch

Checklist: `docs/FORWARD_TEST_LAUNCH_CHECKLIST.md`.
`APP_PROFILE=live python -m src.forward.preflight` gates the launch
(contamination, frozen benchmark, schedule/timing tests, freshness,
accounting). Destructive reinit is refused whenever history exists; archive
via `scripts/archive_prelaunch_live_db.py`, delete the DB file, re-init.
Order baselines: weekly batches order only target *changes* (no drift churn);
monthly/core batches correct drift against holdings.

---

# Phase 2.2: Inception Correction (canonical lifecycle dates)

## 1. The four dates

`benchmark_model_date` (V0.3 freeze) vs `benchmark_snapshot_date` (data end)
vs `forward_test_inception_at` (launch timestamp, Asia/Seoul) vs
`first_execution_at` (first paper fill). Single source of truth:
`forward_state` table (`src/forward/state.py`); NULL = not started, never an
error. A past mislabeling (snapshot date stored as inception) was corrected
via `FORWARD_INCEPTION_CORRECTED` audit event, history left intact.

## 2. Launch

```bash
APP_PROFILE=live python -m src.forward.launch   # one-way gate, double-launch refused
```

Pre-launch, order creation is blocked live-wide and executions before
inception are refused (`RETROACTIVE_EXECUTION_BLOCKED`). NAV rows exist only
after (account-level) first execution, so performance can never predate it.
Invariants (`snapshot ≤ model ≤ inception ≤ first execution ≤ NAV`) are
checked by preflight and unit tests. See
`docs/FORWARD_TEST_LAUNCH_CHECKLIST.md`.

---

# Phase 3B: FastAPI Service Layer (auth added in 3C — see below)

`uvicorn src.api.main:app --reload` (`/api/v1`, OpenAPI at `/docs`,
contract snapshot `outputs/api/openapi_v1.json`, full spec `docs/API_V1.md`).
Routes delegate to services that call the existing forward/risk/portfolio
domain functions (schedule resolver, sleeve funding/guardrail, LW covariance,
metrics, frozen/config readers) — no financial logic is reimplemented in the
API layer. Persistence goes through the SQLAlchemy repositories, so SQLite
and PostgreSQL behave identically; the sqlite3 engine behind the existing
CLIs is untouched. Pre-launch responses degrade gracefully
(`INSUFFICIENT_HISTORY`, `NOT STARTED`, empty lists — never 500).

---

# Phase 3C: Authentication & Authorization (IMPLEMENTED)

- Opaque server-side sessions (`ra_session` HttpOnly + `ra_csrf`
  double-submit CSRF), Argon2id passwords, 7-day server expiry, rotation on
  login, lockout 5×/15min with uniform `INVALID_CREDENTIALS`.
- Roles `user`/`admin`; one user ↔ one participant; IDOR-proof ownership on
  every participant subtree route; `/api/v1/me/*` primary contract.
- Registration gated by `ALLOW_PUBLIC_REGISTRATION` (default closed); team
  CLIs `src.auth.create_admin/create_user/link_user` (hidden password prompt).
- Docs: `docs/AUTHENTICATION.md`, `docs/API_AUTH_MATRIX.md`; OpenAPI
  regenerated (47 paths).

Authentication: IMPLEMENTED / Authorization: IMPLEMENTED.
Public production deployment: NOT YET RECOMMENDED (remaining: HTTPS/reverse
proxy, PostgreSQL primary, production scheduler, frontend, deployment
hardening).

---

# Phase 3D: Next.js Web UI (`web/`)

App Router + TypeScript + Tailwind + Recharts + TanStack Query + Lucide.
Same-origin thin proxy (`app/api/v1/[...path]`) forwards to FastAPI —
HttpOnly session cookies, CSRF header on mutations, no tokens in storage,
no financial logic frontend-side (preview values come only from APIs).

```bash
uvicorn src.api.main:app --port 8000      # backend
cd web && npm run dev                     # http://localhost:3000
```

Pages: `/login`, `/dashboard` (NAV/누적/초과/MDD + Personalized vs Core
360px chart + allocation bars + views), `/portfolio` (Core/Mine/Active table
+ dual bars), `/views` (theme grid ≤2 + reason + submit result dates),
`/performance` (4-line chart + period control + metrics + theme attribution),
`/ranking` (week/cumulative + common/inception + no emails), `/admin`
(role-gated system/users/orders/trades), `/account` (profile/sessions/password).
Design tokens in `styles/design-tokens.css` (spec-exact type scale, 4px grid,
224px sidebar, 8px cards, tabular-nums). Tests: vitest 10 + Playwright
login→view→portfolio→logout E2E (+1440/1024/768/390 overflow) — all green.

---

# Phase 3A: PostgreSQL Schema & Migration (mirror, no cutover)

The live engine still runs on SQLite (`data/forward_test.db`, untouched).
Phase 3A adds a parallel PostgreSQL data layer:

- Reverse-engineered schema: `docs/CURRENT_SQLITE_SCHEMA.md` (15 real tables;
  no `theme_mappings` in source; no declared FKs/indexes in SQLite).
- SQLAlchemy 2.x models (`src/db/models/`, TIMESTAMPTZ/JSONB/NUMERIC,
  VARCHAR+CHECK, all FKs `ON DELETE RESTRICT`, string IDs preserved) with
  SQLite variants for offline verification; repositories with append-only
  discipline (`src/db/repositories/`).
- Alembic (`migrations/`, `0001_initial`); `alembic upgrade head` works,
  `downgrade base` works on dev DBs, offline `--sql` renders PG DDL.
- Migration: `scripts/migrate_sqlite_to_postgres.py [--dry-run]` (empty-dest
  guard, single transaction, orphan FKs fail loudly, source sha256
  before/after). Verify: `scripts/verify_db_parity.py` (counts, full PK sets,
  all fields with per-column tolerances, orphans, financial aggregates,
  canonical hashes).
- Config via `DATABASE_URL`/`DATABASE_BACKEND` (+ `.env.example`);
  `docker-compose.yml` provides postgres:16 for later use.
- Status: `python -m src.db.status`. Operational primary remains **SQLITE**
  (no cutover mechanism exists by design).

Docs: `docs/POSTGRES_SCHEMA.md`, `docs/DATABASE_MIGRATION.md`.
