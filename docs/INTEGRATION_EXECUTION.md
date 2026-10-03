# 2026-10-03 integration

## Scope and evidence

User authorized isolated integration, week 4 operations UI, immutable final decisions,
expected/actual revision review, explicit KEEP/ADJUST choices, local tests and commits.
Production changes, main/develop merges and deployment are excluded.
Base: origin/develop c7c6e20; merged origin/feat/forward-ledger b580762.
Original root and robo checkouts (including existing uncommitted changes) are preserved.
Merge 2fb3781 retains develop rebalance status and all forward database/execution changes.
Baseline: 448 passed, 3 skipped, 1 legacy test failed because _factory now takes a URL.
Corrected that test; focused ledger suite: 25 passed. Frontend baseline: 55 passed.
Database JSON reports are fixture outputs, not evidence of real migration.

## Execution policy

Final confirmation creates an immutable decision and its own target. Date-only prices
cannot identify whether confirmation preceded that day's close, so new decisions
become effective on the next weekday in Asia/Seoul; holidays wait for available prices.
KEEP retains the confirmed composition. It does not freeze quantities, pause scheduled
band-based rebalancing, or cancel pending orders. ADJUST requests redesign; only final
confirmation changes the target. Redesign is blocked while orders are pending.
Managed decisions retain their final weights in scheduled batches; existing financial
bands, costs and execution logic are reused. Legacy records remain readable and are
never given invented original estimates. Unconfirmed capstone participants cannot trade.

Annual model expectations are not subtracted from short cumulative realized returns.
Missing/incompatible metrics include reasons. 3/6 month windows are calendar anniversaries
of the first eligible valuation; period-not-reached is explicit and no results are fabricated.

## External dependencies

Backup PR #12: open, head fb402a8, targets main; integrated backup file is byte-identical.
Do not edit backup.yml. Backup/restore rehearsal and account settings remain separate.
Render source SHA/router and Vercel proxy settings require independent deployed evidence.
Actions/notebook must share the design DB and canonical KST job slot; select one executor.

## AI contribution

Codex inspected and integrated existing teammate code, implemented missing contracts,
record persistence and tests. Existing portfolio/risk/execution engines remain authoritative.
Validation details and remaining dependencies are updated at delivery.

## Delivered contracts and local evidence (2026-10-03 KST)

- Rebalance: reuse `/me/ledger/status.rebalance`; no duplicate `/me/rebalance`.
  Ledger query (`ledger-read-v2`) supplies KRW NAV/cash/holdings, index-100 NAV,
  quantities, prices, order/trade history. Performance and contributions share
  the latest decision's effective-date window and existing calculation engines.
- Decisions: `GET /me/decisions`, `GET /me/decisions/{id}/review`.
  Migration 0007 stores exact confirmed weights, annual model metrics with
  units/basis/frequency, user/account/target/version links, artifact and price
  input hashes. SQLite and PostgreSQL triggers reject UPDATE/DELETE.
- Choices: `GET/POST /me/portfolio/choices`. Ownership, stale version, pending
  orders and repeated request keys are checked. KEEP records retaining composition;
  batches enforce confirmed weights independently of whether KEEP was clicked.
  KEEP is not an execution pause. ADJUST does not place orders; its choice ID is
  attached to the next confirmed decision. Pending orders block redesign confirmation.
- Weekly processing cannot rewrite a managed decision's composition. Daily processing
  uses the confirmed target, and monthly corrections retain existing financial bands.
  Stored order weights remain authoritative at execution, even if newer targets exist.
- `/dashboard` and `/review` connect these real APIs. Historical decisions stay selectable
  and read-only; comparison reasons, actual observation dates and calendar 3/6 month
  not-reached states are displayed. A missing original estimate is never reconstructed.
- Selected base comparison is a labeled gross-price buy-and-hold reference, using the
  captured base weights and identical actual observation endpoints. CORE comparison
  uses the recorded reference account. Neither is presented as a market/safe asset.

Validation:

| Check | Result / evidence |
| --- | --- |
| Full Python 3.11 suite, including isolated PostgreSQL tests | **462 passed**, 16 dependency deprecation warnings; no skipped tests in the final run |
| Frontend unit suite | **56 passed** / 11 files |
| Next production build | Passed |
| Chrome end-to-end flow | Passed: new user -> setup/confirm -> Frontier -> empty history -> KEEP -> ADJUST/reconfirm v2 -> recorded history -> rebalance -> contributions -> revision; second user has no records and cannot read the first user's decision (404) |
| Restart and mobile flow | Passed: re-login after API/web restart retains both decisions and choice history; 390px viewport without page overflow; screenshot visually checked |
| Actual PostgreSQL split DB | Passed: API and batch use the design DB; cross-user rejection; immutable SQL records; 4 concurrent identical choices yield one record; 4 concurrent same-slot job claims yield one executor; auth job count stays zero |
| SQLite -> PostgreSQL mirror | Passed on synthetic browser fixture: 266 rows / 24 tables; source file hash unchanged; zero FK orphans and full-field parity; 2 account NAV identities checked |
| PostgreSQL dump/restore | Passed: custom-format pg_dump, restore into a separate disposable database, repeated source parity check passed |
| Original workspaces | Existing root and nested branches and uncommitted work preserved |

The browser fixture has **SYNTHETIC_TEST** prices for four future weekdays solely to
exercise fills and valuation. Every affected screen labels these synthetic results.
They are not production history, achieved investment returns, or 3/6 month evidence.
The temporary PostgreSQL mirror/restore validates code on that fixture only; it does
not prove production migration, a scheduled backup, or PR #12's recovery workflow.
Generated tracked DB reports and covariance artifacts are restored after tests.

Reproduction (new disposable data directory; never an operating DB):

```sh
APP_PROFILE=validation .venv/bin/python -m pytest -q
# Optional full PostgreSQL checks require separate disposable URLs:
# TEST_DATABASE_URL, TEST_AUTH_DATABASE_URL, TEST_DESIGN_DATABASE_URL.
# Do not use DATABASE_URL/CAPSTONE_DESIGN_DATABASE_URL as test targets.
cd web
npm test
npm run build
```

For the full browser flow, start `scripts/start_lab.py --dev --port 3043 --api-port 8043
--data-dir /private/tmp/<new-isolated-directory>` with the local capstone and market
comparison flags enabled. Its private accounts.json stays outside Git. In web run
`E2E_OPERATIONS_DATA_DIR=<same-directory> npx playwright test
--config=playwright.operations.config.ts`. After a restart, repeat with
`E2E_OPERATIONS_PERSISTENCE=1`. The first test requires fresh users and deliberately
seeds only that disposable local design DB; it cannot safely be rerun on used accounts.

## Read-only deployment diagnosis

The public Vercel deployment is Ready, created 2026-09-22 19:01 KST. Its actual source
SHA is unavailable in returned deployment metadata. Current project settings report
root `web`, production branch `feat/capstone-demo-mvp`, and FASTAPI_INTERNAL_URL host
`robo-capstone-api.onrender.com`. Current settings do not prove the deployment's
historical build environment.

Public `/api/v1/me/ledger/status` returns 404. The target Render server's OpenAPI
returns 200 and includes onboarding and older performance APIs, but excludes ledger
status, contributions and decisions. Thus deployed backend router coverage is behind
this integration. The existing Next proxy path `/api/v1` is retained; recreating local
APIs would not fix that deployed router absence. Render's deployed SHA, source branch,
DB identity and account settings cannot be verified without the owner's access.

The earlier remote daily Action failed with `no such table: themes`; secret names
exist, but their contents and actual DB identities are not observable. Workflow fixes
are local and do not prove a successful production job.

## Account-owner requests and final-review deployment sequence

1. Render/DB owner: confirm the reviewed source commit and `render.capstone.yaml`
   profile. Set distinct persistent authentication `DATABASE_URL` and operational
   `CAPSTONE_DESIGN_DATABASE_URL`, `DATABASE_BACKEND=postgres`, `APP_PROFILE=local`,
   `CAPSTONE_DEMO=1`, `CAPSTONE_MARKET_COMPARISON=1`, secure cookies and registration
   policy. Check the actual source and deployment logs. Existing URLs must be kept
   secret and existing user/ledger data must not be reset.
2. Take both DB backups and perform the separately owned PR #12 recovery rehearsal.
   Review/migrate existing stores explicitly; do not treat checked-in fixture reports
   as operational evidence. Migrate both databases to 0007 before enabling new API.
   The capstone blueprint runs Alembic for both DBs; use one migration executor.
3. Deploy backend first **after final approval**. Verify `/health`, OpenAPI routes,
   authenticated owner-scoped ledger/decisions, correct DB identities and records
   surviving restart. A running process/version 0.1.0 alone is insufficient evidence.
4. Vercel owner: deploy this reviewed frontend, confirm source branch/commit, root web,
   local capstone build flags, and FASTAPI_INTERNAL_URL pointing to that backend with
   no extra `/api/v1` prefix. Recheck cookies/login and the complete production flow.
5. Batch owner: select exactly one executor. Actions requires repository variable
   `FORWARD_EXECUTOR=actions`; notebook requires `.env.local` value `notebook` and
   disabling Actions scheduled jobs. Both URLs/profile must match API configuration.
   Run dry-run before enabling writes. Same-type/slot DB locks are tested; they are
   not a global lock across daily/weekly/monthly types. Actions serializes those
   workflows; disabling the other executor remains necessary.
6. Before the deployment steps above, merge the reviewed integration branch to develop
   through team review, then follow the team's release policy for main. Nothing has been
   pushed, merged to those
   branches or deployed in this work. Backup PR #12 remains a separate main-targeted
   change; coordinate its final commits without overwriting this integration.

## Monday demo and remaining requirements

Monday: the full local flow above is demonstrable. Use a new user to show truthful
waiting/insufficient-history states and a clearly labeled fixture user for history,
contribution reconciliation, KEEP/ADJUST, immutable v1/v2 and revision reasons.
Real post-confirmation observations can only appear after eligible actual price data
and a configured executor. Synthetic future dates must never be called Monday returns.

Priority through Wednesday:

1. Owner settings, reviewed backend/frontend deployment and production flow/restart
   verification; then enable the sole scheduler and verify an actual scheduled job.
2. Production DB migration/backups and PR #12's independent restore proof and recovery
   runbook (both databases, retention, storage credentials and recovery ownership).
3. Agree and supply frozen market/safe benchmark definitions and price data. Until
   then APIs/UI explicitly return `BENCHMARK_DEFINITION_NOT_CONFIGURED`; these two
   comparisons remain incomplete. Selected base and recorded CORE are connected.
4. Accumulate eligible real observations. Short history cannot provide long-horizon
   performance or annual-model-versus-realized differences with mismatched definitions.
   3/6 month persistence/query and not-reached states are implemented; actual periods
   have not elapsed. Legacy initial estimates remain unavailable.

Code implementation and local integration verification are complete for the delivered
scope. Production deployment verification remains incomplete. No completion percentage
or unsupported implementation duration is asserted.

## Commit handoff

Branch: `integration/forward-pg`; workspace: `.work/integration-forward-pg`.
Merge `2fb3781` preserves both source branches. Backend `ca9fa7d` delivers decisions,
contracts and execution policy. Frontend `58e8358` delivers connected screens and
browser tests. The following operations commit contains scheduler alignment,
PostgreSQL migration/recovery validation and this handoff. No remote push is performed.
