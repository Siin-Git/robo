# Integration review and deployment readiness — 2026-10-03 KST

Fixed scope: `integration/forward-pg`, **Draft PR to develop**. The user authorized
this branch's push and PR creation. No new product feature, main/develop merge,
operating DB/provider setting change, deployment or backup PR #12 edit is authorized.
Earlier local-only handoff statements describe earlier stages; this document
supersedes them for GitHub delivery and current read-only provider evidence.

## Remote integration

Fetched origin again: develop **c7c6e20**, forward-ledger **b580762**, unchanged,
both ancestors of HEAD with zero missing commits. Performance, lab-meeting,
market-comparison-reconfigure, v1 integration and capstone-demo heads are also
ancestors. No extra integration/financial-rule change was needed. Original root
and nested robo checkouts, including uncommitted/untracked work, are preserved.

Backup PR #12 is open, head **fb402a8**, targets **main**, separately owned.
Its head is not an ancestor, but `backup.yml` is byte-identical in the integration
(already included through teammate forward work). No backup file/PR edits or
extra backup merge. Coordinate its later changes separately.

## Included scope and limits

- Auth/operating PostgreSQL split, shared API/batch ledger, same-job/slot claims,
  migration 0007 and migration/parity/restore tools. Evidence is local/fixture-only.
- Existing Frontier/base/personalized UI, backend band rules through
  `/me/ledger/status.rebalance`, holdings/cash/KRW NAV vs index-100 NAV, order/trade
  history, contributions, recorded CORE and captured selected-base references.
- Current/pending calendar-effective judgments. Future confirmation preserves
  current performance; after effectiveness new 0/1 observations are insufficient.
  Previous details survive. Performance/contributions/base share decision/window.
- Immutable confirmation/version/provenance, observed-results review and 3/6-month
  persistence/query with explicit period-not-reached states.
- KEEP retains composition; ADJUST requests redesign; final confirmation changes
  the target. **Not order approval/rejection**, execution pause or cancellation.
- **All forecast/actual metric differences are NOT_COMPARABLE/null.** Time passing
  alone does not implement matching period/unit/reference/sampling comparisons.
- Market/safe definitions remain unagreed and explicitly unavailable. No arbitrary
  benchmarks, finance rules or synthetic long-term performance were added.

Evidence: `src/api/services/{decision_service,performance_report_service,reference_service,ledger_read_service}.py`,
`src/forward/{decision_policy,job_runner}.py`, migration 0007, dashboard/review
components and `INTEGRATION_EXECUTION.md` (functional commits and detailed evidence).

## Monday 2026-10-05 local rehearsal

The ordinary pending E2E uses the actual clock: Monday confirmation takes effect
Oct 6. A Saturday confirmation effective Oct 5 must be current on Monday.
The validation-only launcher rehearses Monday **today**, forcing SQLite/empty PG
URLs and fixing only its API subprocess clock to Oct 5 12:00 KST. It rejects paths
outside `/private/tmp` and reused nonempty directories. No product test-clock option.

```sh
# Integration worktree; NEW directory and unused ports each run.
.venv/bin/python scripts/start_monday_demo.py \
  --directory /private/tmp/robo-monday-new-demo --port 3063 --api-port 8063
# Separate terminal, from web:
E2E_MONDAY_DEMO=1 E2E_OPERATIONS_DATA_DIR=/private/tmp/robo-monday-new-demo \
  E2E_BASE_URL=http://127.0.0.1:3063 \
  npx playwright test --config=playwright.operations.config.ts
```

Private accounts.json (0600) stays outside Git. Open `/login` using its relevant row;
never copy passwords to PR/logs. Ctrl+C stops this launcher's two local servers.

1. Participant 1: current v1 effective Oct 1, two synthetic valuations Oct 1–2;
   Monday-confirmed v2 effective Oct 6 pending. Show current/pending, retained
   performance, reconciled contribution and matching reference endpoints.
2. Participant 2: Saturday-confirmed v2 effective Oct 5 current, **zero** valuations;
   v3 effective Oct 6 pending. Show truthful shortage, then “이전 판단 v1 성과 상세 보기”
   to show the preserved two valuations.
3. Participant 3+: fresh unconfigured participant; existing setup/confirm/Frontier/
   history/review flow. Initial effectiveness and record shortage are legitimate.
4. Explain KEEP/ADJUST composition/redesign semantics, incomparable metric reasons,
   unavailable market/safe references and 3/6-month period-not-reached tracking.

Prices are `SYNTHETIC_TEST`, confirmation reasons say synthetic, UI labels
“검증용 합성 데이터 · 실제 운용 기록 아님” remain, and the launcher prints its fixed
clock. This is neither actual Monday returns nor real operating history.

Final local checks on Oct 3: **470 backend tests passed**, including disposable real
PostgreSQL; **59 frontend tests / 12 files passed**; production build with lint/types
passed; **8 effective-boundary API regressions passed**. Monday Chrome E2E passed
both cases above, previous details, matching scopes, 390px without overflow and
zero page errors. Earlier unchanged product commits also passed complete-flow and
restart E2E. PostgreSQL fixture dump/restore is not production recovery evidence.
CI result is reported on the PR; local PG/browser checks are not automatically CI.

## Current accessible provider accounts — read-only evidence

The user notes that the accessible Render account may not be the intended team
account. The following facts apply **only to this accessible workspace**; the
intended Render owner/workspace remains to be identified.

| Item | Observed | Limit / consequence |
| --- | --- | --- |
| Render robo-capstone-api | **MinchoLover/robo**, **main**, live SHA **b06a6bfebef10eb72ac877f0a97621109b508159**, Free | MinchoLover/robo is a fork of Siin-Git/robo. This PR is in Siin-Git; it is not the deployed source. |
| Render start | lab_meeting --from-env, then uvicorn port 10000, workers 1 | No Alembic command. Actual DB revision was not queried. |
| Render env names | Profile/capstone/data-dir/DB-backend/lab/auth keys present; **DATABASE_URL and CAPSTONE_DESIGN_DATABASE_URL absent** from complete list | No evidence of two persistent PG DBs. Masked engine/path values not revealed. |
| Render Disk page | Disks unsupported on Free compute | No attached persistent disk. Current DB contents/persistence require owner check/export. |
| Vercel robo-q3o3 | Git **MinchoLover/robo**, production branch **feat/capstone-demo-mvp**, root **web**, Git deployments enabled | Different repo from this PR; Siin-Git integration push does not update this connected project. |
| Vercel production | READY, dpl_2R8D4gYz9fvBoaZcQjyfy7PKQ8PU, Sep 22 19:01 KST, source **cli**, SHA/branch **null** | Actual production source SHA unavailable. Latest main/b06a6bf Git deployment is a preview. |
| Vercel current env | FASTAPI_INTERNAL_URL host **robo-capstone-api.onrender.com**, empty path; NEXT_PUBLIC_APP_PROFILE=local, CAPSTONE_DEMO=1; lab key present | Proxy matches `/api/v1` routing. Current env is not proof of historical build env. |
| Public backend | Earlier Oct 3 inspection: deployed OpenAPI lacks ledger/status, contributions, decisions. Final readiness retry: health/OpenAPI/direct and proxy ledger requests timed out | Earlier evidence identifies older router coverage. Latest HTTP availability is unverified, not a new 404 claim; do not invent duplicate APIs. |
| Siin-Git Actions | Both DB secret names present; variables empty (FORWARD_EXECUTOR unset) | Values/actual DB identities unknown. PR guard not active on default branch yet. |
| Existing scheduler | Daily Oct 3, weekly Oct 2, monthly Oct 1 on **main/b06a6bf failed**; main has live profile without capstone/DB-backend split | Feature push/PR does not fix scheduled default-branch jobs. Teammate notebook schedules inaccessible. |

No operating DB connection/settings change. Auto-review rejected Render “Show secret”
disclosure; only environment names and safe nonsecret proxy/profile settings were
reported. Masked values are owner-verification items; no secrets were written to Git.

## Required owners and release order — not executed

1. **Team/Render owner:** identify intended account/service. Choose reconnecting to
   Siin-Git/robo or releasing reviewed commits into the fork. Merging this PR alone
   cannot update the currently connected fork. Confirm exact branch/deployed SHA.
2. **DB + backend owners:** export/back up retained data from the nonpersistent old
   service before approved restart/redeploy. Preserve identities/ledger. Set distinct
   persistent auth/operating PG DBs; migrate both to 0007 with one migration executor;
   verify parity/orphans and restart persistence. Reviewed profile: render.capstone.yaml.
3. **Backup PR #12 owner:** independent both-DB backup/restore rehearsal, retention,
   storage credentials and recovery ownership. Coordinate later commits; local
   synthetic restore proves neither production backup nor PR #12's workflow.
4. **Reviewer/release owner:** approve Draft PR, then separately authorize develop
   merge/main release. Backend first; verify routes, owner queries, DB identity and
   migration before frontend. No merge/deploy was performed in this preparation.
5. **Vercel owner:** align source/commit, root web, capstone build flags, backend
   proxy URL without duplicate /api/v1, cookies/login and complete deployed flow.
6. **Batch + repo owners:** choose Actions or notebook and disable the other; align
   API/daily/scheduled_jobs operating DB and secret identities. Updated workflows
   must reach default branch before their guard affects schedules. Set
   FORWARD_EXECUTOR=actions only if chosen; dry-run, then verify eligible real job.
   Same-job/slot claims do not replace cross-job/machine execution coordination.

Unagreed market/safe definitions and forecast/actual methodology remain outside
this PR. Actual 3/6-month observations remain future work. Local/CI completion and
production deployment verification are separate statuses.
