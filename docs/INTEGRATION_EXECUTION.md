# 2026-10-03 integration

## 2026-10-05 ledger ranking presentation

The default recorded-ledger comparison now uses the existing demo card/table/chart presentation. Financial figures, missing observations and risk quality gates are preserved. Public period theme IDs/metric averages and independent server return ranks are additive read-only fields. Scope, actual validation, isolated preview and limitations are recorded in [LEDGER_RANKING_PRESENTATION.md](LEDGER_RANKING_PRESENTATION.md). No operation, replay execution, scheduler, merge, push or deployment was performed.

## 2026-10-04 최신 운영 인수 범위

PR #19/#20의 기능 통합·영속 DB 배포 준비는 develop `250f315`에 병합됐으며 develop/릴리스 후보 `857d2d1`/개인 fork 릴리스 CI가 모두 성공했다. Draft PR #21은 main에 병합하지 않았다. 사용자가 개인 Render 계정의 MinchoLover/robo 비공개 fork 배포를 결정했고 두 브랜치가 같은 커밋으로 복사된 것을 읽기 전용 확인했다. 개인 main은 `b06a6bf`로 보존됐다.

사용자가 새 운영 원본을 3073의 현재 두 SQLite로 확정했다. 인증 15명, 판단 3·주문 8·가격 42,010·체결/평가 0, head 0008과 백업 대비 핵심 기록 보존을 최종 읽기 전용 검증했다. 기존 07:30 daily와 3073은 유지한다. 이번 남은 작업은 CI·문서·로컬 검증이며 main 병합·Render/Vercel·운영 DB·예약 변경은 별도 대화에 인계한다. 팀원 Neon을 덮어쓰지 않는다.

실제 SQLite 백업→폐기 PG 이전→PR #12의 두 덤프→다른 빈 폐기 PG 복원은 완료했고 원격 운영 이전과 구분한다. Python 511+35, Vitest 67, production 빌드, Chrome 격리 흐름 6개 통과. 상세 CI 링크·데이터·예약·백업·후속 운영 검증은 [PUBLIC_OPERATION_RELEASE.md](PUBLIC_OPERATION_RELEASE.md)에 기록했다. 아래 과거 scope 및 PR #12 open 표기는 당시 기록이다.

## Scope and evidence

User authorized isolated integration, week 4 operations UI, immutable final decisions,
expected/actual revision review, explicit KEEP/ADJUST choices, local tests and commits.
Production changes, main/develop merges and deployment are excluded.
The later GitHub instruction permits integration-branch push and a develop-target
Draft PR only; current scope/evidence is in `PR_DEPLOYMENT_READINESS.md`.
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
Expected-versus-actual metric differences are currently ALWAYS NOT_COMPARABLE with
null differences. Elapsed time alone cannot complete comparison: matching period,
units, reference and sampling definitions require a further agreed design and implementation.

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
  the current KST-effective decision's window and existing calculation engines.
  Future confirmations remain pending and do not replace this report's decision.
- Decisions: `GET /me/decisions`, `GET /me/decisions/{id}/review`.
  Migration 0007 stores exact confirmed weights, annual model metrics with
  units/basis/frequency, user/account/target/version links, artifact and price
  input hashes. SQLite and PostgreSQL triggers reject UPDATE/DELETE.
- Choices: `GET/POST /me/portfolio/choices`. Ownership, stale version, pending
  orders and repeated request keys are checked. KEEP records retaining composition;
  batches enforce confirmed weights independently of whether KEEP was clicked.
  KEEP/ADJUST are composition/redesign choices, not order approval/rejection.
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

Initial delivery validation (before independent review; current follow-up results below):

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
APIs would not fix that deployed router absence. At that earlier stage, Render SHA/branch/DB settings were unverified. Subsequent
read-only inspection is in `PR_DEPLOYMENT_READINESS.md`; intended team account
identity and actual operating DB revision remain open.

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
   branches or deployed in that local delivery stage. The later GitHub instruction
   permits integration push and a Draft PR only. Backup PR #12 remains a separate main-targeted
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
4. Accumulate eligible real observations for actual outcome tracking. Separately agree
   and implement period/unit/reference/sampling alignment for expected-versus-actual
   differences. The current API ALWAYS returns NOT_COMPARABLE and null differences,
   even when a tracking horizon is reached. 3/6 month persistence/query and not-reached
   states are implemented; actual periods have not elapsed. Legacy initial estimates
   remain unavailable. KEEP/ADJUST do not implement order approval or rejection.

The delivered implementation covers immutable judgments, observed-results review and
composition/redesign choices. Numeric expected-versus-actual differences, order
approval/rejection and undefined market/safe benchmarks are outside that completion
claim. Code implementation and local verification are complete only for this scope. Production deployment verification remains incomplete. No completion percentage
or unsupported implementation duration is asserted.

## Commit handoff

Branch: `integration/forward-pg`; workspace: `.work/integration-forward-pg`.
Merge `2fb3781` preserves both source branches. Backend `ca9fa7d` delivers decisions,
contracts and execution policy. Frontend `58e8358` delivers connected screens and
browser tests. The following operations commit contains scheduler alignment,
PostgreSQL migration/recovery validation and this handoff. No remote push was performed in that delivery stage; later GitHub preparation
is recorded separately.


## Independent-review follow-up brief (2026-10-03 KST)

Problem: confirming a revision effective on 2026-10-05 immediately switched the
2026-10-03 dashboard start date and hid two existing valuations. The selected-base
comparison independently used the latest confirmation, so simply fixing the NAV
filter would still compare against the wrong base snapshot.

Primary journey: view v1 performance -> confirm future v2 -> keep seeing v1 performance,
contributions and captured base -> inspect pending v2 -> on its effective date show
v2's own observations (including 0/1 insufficient states) -> revisit preserved v1.

Acceptance and decisions:

- Determine current operation by KST calendar effective date, not confirmation order
  or most recent valuation date. "Current" does not assert that a fill has occurred.
- Return `decision_context` with active/pending/previous summaries and report ID/window.
  Both dashboard and contribution endpoints use this common resolver. Reference
  comparison uses that report ID and actual observed endpoints without picking latest.
- Before effectiveness preserve the existing active performance. At effectiveness
  switch the reporting decision even if new valuations are absent; do not label old
  returns as new performance. Keep a direct previous-decision detail link.
- Managed dashboard windows exclude future valuations. Explicit decision details keep
  their own original-effective-to-successor-effective historical window.
- Test before/after effectiveness, 0/1/2 new valuations, UTC-to-KST midnight, initial
  pending user, ALL/1M contracts, selected base selection and historical details.
- Confirmation invalidates cached decision reviews along with dashboard/decision queries,
  so successor-window metadata is refreshed during the ordinary navigation flow.
- UI and handoff must say KEEP/ADJUST are composition/redesign choices, not order
  approval/rejection, and current expected/actual metrics are all NOT_COMPARABLE.
- No finance-rule changes, migrations, operating DB writes, merges to main/develop,
  push, deployment, or modifications to backup PR #12. Reuse this worktree/history.

This follow-up supersedes the earlier claim that "latest confirmed" anchors the
performance window. Earlier PostgreSQL migration/restore evidence remains fixture-only.

Follow-up validation and reproduction evidence:

| Check | Follow-up result |
| --- | --- |
| Exact reproduction before patch | Regression failed as expected: `observations` became 0 after future confirmation; expected 2 |
| Same reproduction after patch | 2 -> 2; return metrics unchanged; selected-base comparison remains AVAILABLE, preserves its original return and decision ID |
| Effective-date and insufficient-history regression | 8 tests passed: ALL/1M, before effectiveness, future records excluded, 0/1/2 new valuations after effectiveness, KST midnight, initial pending user, preserved previous details and matching reference snapshots |
| Full Python suite with disposable PostgreSQL | **470 passed**, no skipped tests; 16 dependency deprecation warnings |
| Frontend unit tests | **59 passed**, 12 files; current/pending, insufficient new history and previous-detail link covered |
| Production build | Passed, including Next lint/type validation; the final rerun stopped dev first and preserved duplicate generated development types outside the worktree |
| New Chrome regression | Passed without a forced refresh: login -> existing v1's two synthetic valuations -> ADJUST/reconfirm future v2 -> portfolio link returns to retained v1 dashboard -> identical contribution/reference scope -> pending v2 detail empty -> direct v1 detail retains records |
| Existing Chrome complete flow | Passed again on separate fresh fixture users; future initial decisions correctly have no current dashboard performance; KEEP confirmation selector distinguishes it from the synthetic banner |
| Mobile and runtime errors | 390px dashboard has no page overflow; current/pending panel screenshots visually inspected; zero browser page errors in both flows |

The additional fixture helper `scripts/seed_pending_decision_fixture.py` accepts only
fresh `/private/tmp` lab accounts and backdates the first confirmation **inside its
isolated subprocess** to reproduce existing history. It never rewrites immutable
records or enables a test clock in the running API. `SYNTHETIC_TEST` prices/returns
and the fixture decision reason explicitly identify this as test data, not actual
historical operation or backfilled initial estimates for existing users.

For a fresh follow-up demo, start the local lab in a new disposable directory as above,
then run `.venv/bin/python scripts/seed_pending_decision_fixture.py --directory <dir>`.
In web run `E2E_PENDING_DECISION=1 E2E_OPERATIONS_DATA_DIR=<dir>
E2E_BASE_URL=http://127.0.0.1:<web-port> npx playwright test
--config=playwright.operations.config.ts`. This scenario uses the running API's actual
calendar: Oct 3 confirmation is effective Oct 5; Oct 5 confirmation is effective
Oct 6. Automated API regressions
control their own clocks and cover both sides of that date independently. The browser
flow consumes fresh fixture users and must not be rerun against their completed state.

Monday demonstration scope after this follow-up:

- Before new effectiveness, show current v1 and pending v2 together while v1's
  performance/contributions/captured base remain visible. This was verified on Oct 3.
- At or after Oct 5, current v2's 0/1 observation state is accurately insufficient.
  Its previous v1 detail remains accessible. Calendar-transition behavior is API-tested;
  it was not claimed as a real future browser/production event on Oct 3.
- Demonstrate immutable original/versions, composition KEEP/redesign ADJUST choices,
  and read-only observation review. Do not demonstrate these as order approval/rejection.
- Expected-versus-actual numeric differences remain unimplemented: all current metric
  comparisons return NOT_COMPARABLE, difference=null. Elapsed 3/6 months alone does
  not make these comparable. Market/safe benchmark definitions remain team agreements.

Operating-owner work after review remains separate:

- This patch adds no schema migration or provider-setting requirement. Deploy the
  reviewed backend and frontend together through the team's existing release process;
  older deployment/DB separation tasks in the earlier handoff still require owners.
- After any future approved deployment, verify current/pending scope using real owner
  accounts, the actual deployed commits, the correct persistent DBs and restart behavior.
  No production validation or provider changes were performed in this follow-up.
- Select one batch executor and verify eligible real observations; do not populate
  future production results to make a demo chart. Agree benchmark definitions and
  expected/actual comparison methodology separately. Backup PR #12 remains untouched.

Local implementation, local verification and additional commits are complete for this
review fix. main/develop, remote pushes, operating DBs and deployment remain unchanged.

The backend follow-up is committed as `dc0b27a`. Frontend follow-up `813795d`
contains current/pending display, direct historical review links, confirmation cache
refresh, clarified feature scope and the synthetic browser reproduction helper/tests.
The subsequent documentation commit records this evidence and supersedes the old
completion wording. Earlier commits are preserved without amendment.

The later `PR_DEPLOYMENT_READINESS.md` records fixed PR scope, remote/provider
inspection, owner responsibilities and the independently verified disposable
Monday-clock browser rehearsal. This synthetic rehearsal does not prove production.

## Separate persistent local operation (2026-10-03)

The later user-authorized local operation is on `feat/local-forward-operation`,
forked from review commit `c587dae`. It does not expand the frozen integration PR.
`LOCAL_REAL_OPERATION.md` records real-clock SQLite isolation, live market input,
one registered macOS daily agent, restart/dedup evidence, controls and limitations.
The synthetic Monday servers/data remain separate. No remote DB, push, merge,
deployment or backup PR #12 changes were made. Real user fills/valuations remain
pending confirmation and eligible post-effective market prices; disposable tests
are explicitly distinguished from actual local operating records.

## Backup PR #12 follow-up authorization (2026-10-03)

The user took over PR #12 and explicitly superseded the separately-owned restriction.
Only backup validation, an isolated actual restore test and its documentation change.
The same patch is applied on the PR #12 head and this develop candidate; develop is
never merged wholesale into the main-target backup PR. PostgreSQL backups do not
cover the persistent local SQLite operation. See POSTGRES_BACKUP.md for evidence,
required target/version checks and the separately gated main activation/operating
recovery status. Existing local apps, operating data and daily LaunchAgent are preserved.

### Read-only connection diagnosis follow-up (2026-10-03)

The user narrowed the task to the design connection failure. Actions run
37119843115 compared native libpq and the converted environment with the same
secret/client: malformed URI query, raw controls and an invalid channel-binding
value were identified; the previously successful code ignored that option.
Minimal URI validation/encoding corrections and safe diagnosis have 35 local
backup/restore regression passes. Secrets/security requirements and BACKUP_*
approval variables were not changed. Main/operating backup remain held; the
owner must privately correct only the design URI and confirm actual app wiring.

## Develop integration verification (2026-10-03)

After PR #13 merged as `0366279`, the user requested integrating the completed
persistent-local-operation work into develop before broader graph/data-source
changes. `DEVELOP_INTEGRATION_VERIFICATION.md` records the isolated integration,
PostgreSQL test-initialization correction, 477 backend tests, 59 frontend tests,
build/type checks and both Chrome flows. Earlier statements about no merge or
push describe those earlier stages; this delivery authorizes develop integration.
Production deployment, main, remote DBs and backup PR #12 remain separate.


## 2026-10-04: 초기 Frontier 주기 선택 (로컬 전용)

`feat/initial-rebalance-settings`는 develop `f3110f6`에서 분리했다. 첫 Frontier의
기존 설정 영역에 monthly/quarterly를 연결하고 최종 결과에는 읽기 전용 요약만 추가했다.
사용자별 저장 경로가 없었던 점을 확인하고 기존 onboarding API·immutable 판단 JSON·
월간 엔진의 기존 주기 판정을 최소 보완했다. 변경/검증/시연 경로와 예약 실행의 한계는
[INITIAL_REBALANCE_SETTINGS.md](INITIAL_REBALANCE_SETTINGS.md)에 기록했다.
이전 백엔드 504 passed/16 skipped 보고는 0008의 마지막 변경을 포함하지 못했으므로
아래 회귀 수정의 최종 결과로 대체한다. 기존 프론트 62 passed, 타입 검사/프로덕션 빌드와
데스크톱·모바일 E2E 2 passed는 초기 기능 커밋의 화면 검사이며 이번 백엔드 수정에서 재실행하지 않았다.
기존 실제 앱·운용 DB·예약 실행·원격 설정은 그대로 유지했으며 푸시·병합·배포는 하지 않았다.

### 0008 오프라인 마이그레이션 회귀 수정

`72dbb2f`의 기존 오프라인 PostgreSQL DDL 검사가 MockConnection inspection으로
실패함을 재현했다. `9da434c`는 SQL 생성 시 inspection 없이 ADD COLUMN을 생성하고,
온라인에서는 기존 컬럼 감지를 유지한다. 기존 테스트를 보존하고 회귀 6개와
필수 ALTER SQL 검사를 추가했다. nullable 기존 값·저장 주기·불변 판단·사용자·목표·주문을 보존한다.

Python 3.11.15 최종 전체 백엔드 **528 passed / 0 failed / 0 skipped**.
마이그레이션·모델·주기 API 관련 **30 passed**, 개인별 배치 **1 passed**.
새 SQLite 전체 적용/되돌리기, 0007 upgrade, 컬럼 사전 추가 후 반복 upgrade를 검증했다.
별도 PostgreSQL 14.19(127.0.0.1:55494)의 새 DB·0007·사전 컬럼/주기를 검증했고,
오프라인 생성 SQL도 빈 DB에 오류 시 중단 설정으로 실제 적용했다.
기존 라이브 PG API/DB/인증·운용 분리/복원 검사도 최종 전체 실행에 포함했다.

증거는 [INITIAL_REBALANCE_SETTINGS.md](INITIAL_REBALANCE_SETTINGS.md) 및
`/private/tmp/robo-migration-0008-g_738wxd/`에 있다. 폐기용 클러스터만 종료하고,
기존 5432 DB·로컬 앱/운용 기록/자동 적립·Render/원격 DB는 변경하지 않았다.
테스트 생성 보고서/계산 산출물은 원복하고 이 수정 및 인수 문서만 로컬 커밋한다.
푸시·병합·배포는 하지 않는다. 후속 문서 커밋에는 실행 코드 변경이 없다.

## 2026-10-05 운영 가격 자동 수집 복구

운영 `release/public-operation`의 `b6add639`를 기준으로 독립 checkout에서 수정했다.
07:30 KST 예약이 한국 장중에 늦게 시작하면 수집 전체가 차단되던 경로를 가격 전용
`src.forward.run_prices`로 분리한다. 최초 결정효력일 2026-10-05 이후의 종료된 실제
세션만 수집하고 정확히 같은 날짜 FX로 환산한다. 기존 행은 불변이며 새 가격만 추가한다.
주문·체결·NAV·job/event·schema와 3073/3099/3103 원본은 변경하지 않는다.
주간/월간은 별도 거래 활성화 변수로 잠그고 공동 T0 통합 전 자동 거래를 시작하지 않는다.

수집기·세션·workflow 집중 검사 45 passed(폐기 PostgreSQL 실검사 6개 포함), 전체
백엔드 598 passed/22 skipped. 이후 추가 provider 검사 3개는 집중 검사에 포함했다.
DB 강제 읽기 전용, 가격 외 전체 검사표 보존, 롤백, 중복·같은 날 재시도, 부분 실패를
검증했다. 테스트 생성 보고서/위험 공분산 파일은 복원했다. 상세 계약/실행/CI/반영 경계는
[CLOUD_PRICE_COLLECTION.md](CLOUD_PRICE_COLLECTION.md)에 기록했다. 구현 담당은 로컬
커밋까지만 수행하며 운영 preflight/PR/CI/병합/실제 전후 검증은 배포 담당이 이어간다.

## 2026-10-04 원장 성과·그래프·참여자 비교 후속 구현

PR #18 이후 develop `cb5c778`에서 `feat/ledger-performance-ranking` 전용 worktree로 작업했다. 기본 performance/ranking을 현재 목표 비중의 과거 가격 비교에서 실제 운용 원장 조회로 연결한다. 기존 dashboard·기여도 계산과 CORE_V0.3, 현재/대기 판단 및 과거 판단 조회를 유지한다. 공통 실제 관측 구간으로 성과·기여도·참여자 비교를 맞추고, 0/1건 평가와 비교 불가 사유를 정확히 표시한다. 과거 가격 비교/시연 기능은 `source=demo`에서 유지한다.

상세 출처·API·검증 및 실행 절차는 [LEDGER_PERFORMANCE_RANKING.md](LEDGER_PERFORMANCE_RANKING.md)에 기록했다. 기존 실제 날짜 3073 앱과 원장/계정/스케줄러는 보존했고 새 구현은 별도 3085 합성 테스트 환경에서 검증했다. 이번 단계는 로컬 커밋까지이며 push/merge/deploy 및 원격 DB 작업은 하지 않는다. 실제 운용 원장에 테스트 데이터를 추가하지 않는다.

### 독립 검토: 내부 실제 관측과 위험 순위 보존

공통 날짜 교집합으로 중간 NAV를 제거해 A의 100→50→100 MDD가 -50%에서 0%로 바뀌던 회귀를 수정했다. 공통 시작·종료 평가일만 맞추고 내부 원본 기록은 기존 성과 계산기에 모두 전달한다. A 지수 50은 보존되고 B 누락 날짜는 null이며 선을 연결하지 않는다. 평가 공백/오래된 가격이 있는 관측 MDD와 위험 순위 자격을 구분하고, 연율 변동성의 기존 유효 수익률 30개·품질 조건은 별도로 표시한다. 수익률은 B +1% 1위/A 0% 2위 유지, MDD 순위는 품질 적합 비교 인원 부족으로 보류한다.

최종 전체 백엔드 546 passed/0 skipped(폐기용 PostgreSQL 포함), 관련 회귀 34 passed, 프론트 67 passed, production build/타입 검사 통과. Chrome 기존 흐름 2개 + 정확한 공백 사례 2개(데스크톱/모바일) 통과. 상세 재현/환경 오류 정정/로그/실행 절차는 위 인수 문서의 독립 검토 수정 절에 기록했다. 새 수정 화면은 격리된 3086/3087이며 기존 3073/8073·실제 DB/예약 실행·기존 프리뷰는 보존한다. 스키마/배치/스케줄러 변경과 push/merge/deploy는 없다.


## 2026-10-04 신규 전략 자료·예상/실제 비교 후속

사용자 지정 기준 09e92ad에서 별도 feat/strategy-comparison worktree로 작업하고, 해당 검증 커밋을 포함한 최신 develop 250f315 위로 정리했다. 제공 네 파일은 참고 자료로 읽어 연구 조회에만 등록했다. 주도주 변형/신호 시점, 수출 과거 모델/미래 Active를 구분하며 모델 지수를 거래 가격이나 실제 원장에 넣지 않는다. 예상/실제는 동일한 저장 정의에서만 차이를 계산하고, 미합의 시장/안전자산은 후보와 승인 정의 연결 경로만 제공한다.

[STRATEGY_COMPARISON_HANDOFF.md](STRATEGY_COMPARISON_HANDOFF.md)에 자료 근거/미결정 질문/변경 파일/검사/시연과 수요일 작업을 기록한다. 이 세션은 사용자 추가 조건에 따라 기능 커밋/작업 브랜치 푸시/develop Draft PR까지만 담당한다. develop/main 병합·실제 배포·Render/Vercel/운영 DB/공유 secret/배포 workflow 변경은 수행하지 않는다. 3073과 기존 실제 DB/예약 실행은 보존하며 검사는 임시 DB/3091·8091/별도 빌드에서 수행한다.

## 2026-10-04: 15명 공동 시작 제어만 구현

최신 원격 `release/public-operation`의 `b6add63`을 기준으로 별도
`.work/competition-start`, `feat/shared-competition-start`를 만들었다.
기존 체크아웃/미커밋 변경, 실제 3073 앱/계정/운용 DB/예약 실행은 보존했다.

기존 인증 `DemoCohort`/`DemoSlot`과 운용의 불변 판단으로 전원 READY를 확인하고,
운용 `forward_state`의 `competition_start`·개별 참가자/최초 판단 참조·기존
`forward_test_inception_at`에 미래 한국 날짜 T0를 한 번만 저장한다. 신규 테이블이나
마이그레이션 없이 기존 값 길이 제약을 지킨다. 실제 한국 시각이 T0에 도달하기 전에는
프로필 local에서도 최초 주문/체결/holdings/NAV를 차단한다. 일간 및 직접 엔진 호출,
주간/월간 경로에 같은 조건을 적용한다. 기존 financial 엔진·비용·초기 금액·밴드는 유지한다.

기존 pending은 삭제/날짜 덮어쓰기 없이 보존하며 T0 이후 가격만 체결에 사용한다.
호환되는 최초 pending은 재사용하고 충돌 주문/기존 운용 기록/초기 자금 불일치는
T0 예약을 거부한다. 예약 시점 판단을 최초 구성으로 유지하고 후속 버전도 보존한다.
대기 job은 기존 skipped 이력으로 남겨 같은 날짜 재시도가 가능하며 실행 잠금·성공
job의 중복 방지는 그대로다. T0 도달 후 이전 날짜 가격만 있으면 정상 평가 대기다.

최종 Python 3.11.15 전체 백엔드(CI의 `tests --ignore=tests/backup`) **569 passed /
0 failed / 0 skipped**, 폐기용 PostgreSQL 18과 SQLite 포함. 새 공동 시작 검사 24개는
2명/15명 전원 흐름, T0 전/후, 기존 pending, 직접 호출, 동일 Actions 환경과 실제
daily CLI(강제 실행 없음), 늦은 종가, 반복 실행/재연결, 충돌·인증 실패·명단 변경,
불변 판단/재설계·기존 이후 주문 규칙을 검증했다. 기존 15명 실제 API 확정/조회/
재시작 테스트도 수정 후 통과했다. 프론트 **71 passed (16 files)** 및 production
build/타입 검사 통과. UI 변경은 없고 이번에는 추가 브라우저 검사를 수행하지 않았다.

Actions workflow/secret/스케줄러는 변경하지 않았고 운영 DB에 T0를 예약하지 않았다.
실제 runner와 실제 공동 체결은 운영 미검증이다. 기본 실행 브랜치에 코드 반영,
실제 15명 READY/동일 초기 자금/충돌 pending 확인, 미래 T0 합의·예약이 남았다.
원격 push/merge/deploy, history backfill, TIPS·랭킹·기여도·±10%p·알림·백업 PR #12와
다음 기능은 진행하지 않는다. 상세 명령/차단 위치/적용 한계는
[SHARED_COMPETITION_START.md](SHARED_COMPETITION_START.md)에 기록했다.

## 2026-10-04: 별도 로컬 15명 가격 재생과 시연

개인 저장소 `MinchoLover/robo`의 release `b6add63`와 공동 시작 `dff6a58`을 기준으로
`.work/competition-replay`/`feat/competition-replay`에서 진행했다. 팀 develop `250f315`와
개인 배포 브랜치를 혼동하지 않았다. 기존 원장 성과·기여도·랭킹/전략 자료 조회를 재사용했다.

새 시연 15명을 기존 최종 확정 API로 준비하고 원본 판단 날짜를 유지한 채 별도 SQLite
실행 UUID와 manifest/상태/잠금/체크포인트로 기존 주문·체결·평가 엔진을 과거에 적용했다.
외부 가격은 Yahoo 원본이며 최근 완전한 공통 관측일 10개(9/16–10/2, 연속 거래일 아님)를
사용했다. 원본 결측을 채우지 않았고 30계좌의 주문/체결268건·보유평가2,680건·NAV300건을
생성했다. 개인/기여도/CORE/랭킹의 동일 기간 수치와 회계 정합성을 확인했다.

실제 판단/Revision/3·6개월 조회는 원본 설계 DB, 재생 성과 조회만 읽기 전용 별도 원장이다.
소급 체결/공동 시작 차단은 전역 해제하지 않았다. 일반 daily는 replay DB에서 차단된다.
반복/준비 및 체결 직후 중단·재개/부분 완료 랭킹 차단/manifest 보호를 검증했다.
별도 복사본의 미래 일간 연결에서 초기 주문 증가 없이 NAV30건을 추가했고 동일 날짜 중복은
없었다. 이 결과는 격리 fixture 검사이며 운영 시작이나 미래 실가격 관측이 아니다.

백엔드 최종 576 passed(폐기용 PostgreSQL18+SQLite, skip0), 프론트74 passed 및 빌드/타입 검사,
대표03 실제 브라우저 데스크톱/390px 모바일 2 passed. 새로고침·재로그인·15/15 유지·결측선
끊김·위험 순위 보류·판단 원본 조회를 확인했다. 3097/8097 시연 서버를 같은 DB로 재시작해
기록 유지도 확인했다. 기존3073/8073·운영DB·자동운용 예약은 보존한다.

읽기 전용 Actions37208198285에서 실제 Actions 대상의 계정15/설계 확정사용자1·판단3버전,
체결·평가0을 확인했다. Render의 대상 일치와 전체 READY는 별도 상태이며 로컬15/15로
대신하지 않는다. 추가 read-only Actions37211864102에서 공동 gate 기준 READY1/15·T0 null을
확인했다. 주도주/수출 구성 snapshot은 기존 연구 자료, ETF/자산별 실제 가격·보유
추적과 구분한다. 내부 기업 후속 추적은 확인되지 않아 중복 개발하지 않았다.

명령·5분 시연·교수님 요구사항 대조·캡처·한계는
[LOCAL_COMPETITION_REPLAY.md](LOCAL_COMPETITION_REPLAY.md)에 기록했다.
푸시와 Draft PR은 사용자 승인 범위이며 병합/배포/운영bootstrap/T0예약/PR12수정은 하지 않는다.


## Dashboard disclosure UI (2026-10-05)

See [DASHBOARD_DETAILS_UI.md](DASHBOARD_DETAILS_UI.md) for the isolated frontend changes, preview, and validation. Frontend 74 tests passed; final production build and desktop/mobile browser validation passed. Financial logic and backend were not changed.
## Yahoo daily session-date correction (2026-10-05)

Continued the existing Draft PR in an isolated worktree; reused UI cc9bfe8 via
cherry-pick 02cf3eb. Corrected IANA exchange-session labels and first-query boundary
coverage, preserved the original demo/configuration and rebuilt a new real-price
ledger for the identical 9/16–10/2 period (11 observations). No finance engine,
order timestamp, operating DB/T0/scheduler or backup workflow was replaced.
589 backend and 75 frontend tests pass; build and two Chrome viewport flows pass.
See [YAHOO_SESSION_DATE_FIX.md](YAHOO_SESSION_DATE_FIX.md) for before/after numbers,
requested independent audits, professor requirement limits and operational recovery.


## Midterm demo freeze — 2026-10-05

3099 is the sole demonstration baseline: code41b4bdd, same9/16–10/2 period,11observations,15/15complete, P003+0.21127061%/CORE+0.18845140%,rank11. Replaced earlier3097 instructions in LOCAL_COMPETITION_REPLAY.md and marked historical UI-only figures. No app/financial/API change. Private consistent SQLite/code backup and disposable restore validation are recorded in <workspace>/.work/demo-backups/midterm-3099-20261005/freeze.json. The revised5-minute flow and requested independent professor requirement audit distinguish stored selected Frontier point from full historical curve and user Revision from unimplemented internal administrator Revision. Operating scheduler/T0/deployment remain separate and unchanged.
