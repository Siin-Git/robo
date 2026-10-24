## 2026-10-23 · 판단 검증 자동 갱신 보완

기존 daily-forward의 활성화와 최근 예약 성공을 읽기 확인했다. 검증 패널에
60초 자동 조회, 실패 시 이전 자료 안내, 일일 평가 작업 상태, 동일 판단의
검토 기록 화면 연결 및 저장 후 캐시 갱신을 추가했다. 최초 판단은 보존한다.
누락 CORE 버전/불완전 좌표를 실적으로 해석하지 않고, 당시 산출 근거를 표시한다.
로컬 API/성과 계산 215 통과·PostgreSQL 전용 1 건너뜀, 프런트 110 통과 및 빌드 통과.
상세와 한계는 docs/FRONTIER_DECISION_VERIFICATION.md에 기록했다.
운영 배포·실거래·예약 설정 변경 없음.

# 2026-10-03 integration

## 2026-10-23 Frontier 투자 판단 검증

원본 `release/public-operation@8bee054`에서 `feat/frontier-decision-verification`
브랜치로 구현했다. Base/Personalized 점을 선택하면 당시 판단·동일 기간 NAV
비교·당시 가정의 재검토를 표시한다. 기존 불변 판단 JSON을 재사용하며 미확보
예상값과 실적을 생성하지 않는다. 현재 자산/전략 비교는 접힌 상세로 보존한다.
데이터 경계, 설계 결정과 검증은 [FRONTIER_DECISION_VERIFICATION.md](FRONTIER_DECISION_VERIFICATION.md)에 기록했다.
운영 배포, 운영 DB 변경과 거래 실행은 수행하지 않았다.

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

## Separate internal-tracking integration — 2026-10-05

The later user-supplied worktree proves that full Frontier-coordinate capture and
administrator review already exist on `feat/decision-asset-tracking` at
`6cd16d8`, `e8298c8`, `4aca339`; they were absent from the frozen3099 branch.
Read the provided professor transcript and reused that implementation on
`integration/internal-tracking-demo`, based on `3419ca1`, instead of creating it
again. The isolated3103 environment preserves all15 demo participants and reads
actual decision observations from the original design DB, excluding the separate
past-price replay. New confirmation captures50 Frontier coordinates; legacy
missing values remain missing. Administrator notes are permission/CSRF protected,
idempotent and do not change targets/orders; customer APIs exclude those records.

Final local CI-range backend:599passed/0failed/0skipped, including disposable
PostgreSQL18.6 UTF-8 split-DB/concurrency tests; frontend81passed/19files and
production build/lint/types pass. Chrome1440/390px: existing replay2passed and
internal tracking2passed. New financial thresholds/drift-alert changes from the
old source were deliberately excluded. No new migration, scheduler, operating
data/T0 rewrite, remote push/merge/deployment or PR12 change.
See [INTERNAL_TRACKING.md](INTERNAL_TRACKING.md) for exact source boundaries,
professor requirements, local accounts/data, restart commands and remaining limits.
The frozen3099 source/data/docs remain unchanged; this section describes3103 only.


## 2026-10-05 local 3103 real-price tracking

See [PRICE_TRACKING_AUTOMATION.md](PRICE_TRACKING_AUTOMATION.md). Reused session-date parsing and incremental price conversion; added completed-session filtering, exact observed-date mode and an explicitly local prices-only hourly worker. Existing 3103 admin reports already poll every 15 seconds. No historical replay, trading start, decision, order, NAV, operating Neon or original scheduler changes. Real collector and unique launchd invocation completed with 0 new rows / 0 failures while waiting for observations on or after the decision effective date. Local and durable backup evidence, regression counts and limitations are recorded in the dedicated document.

## Unified personal-repository review — 2026-10-05

User requested one GitHub review for all implemented work. Preserved existing focused commits and merged operating release `efc67649` and local tracking `2ed955d` into the ranking presentation branch. The resulting head updates Draft PR #1, targeting `release/public-operation`; no operating release merge or deployment is included. Operating price-only workflows and backup code are preserved exactly. Root/web Vercel configuration continues to disable deployment of `feat/competition-replay`.

The later user request connects graphs across confirmed holidays. Only empty `MARKET_CLOSED` dates are omitted from chart display; actual observations and unknown missing dates remain. Backend/API figures and risk quality rules are unchanged. Full backend 682 passed with disposable PostgreSQL/restore checks, frontend 86 passed, build/types passed, and six Chrome desktop/mobile flows passed. See [CAPSTONE_UNIFIED_HANDOFF.md](CAPSTONE_UNIFIED_HANDOFF.md) for current verification, source commits, local preview, operational limits and remaining team definitions. Earlier sections retain their original milestone status.


## 2026-10-05: Actions 일간 운용 dry-run → 승인 실행 준비

- 개인 기본 브랜치 `release/public-operation` / `6f94193` 기준 별도
  `fix/actions-stored-forward` worktree에서 수정. 제공된 dry-run 성공 링크는
  `b6add63` 버전이고 최신 가격 전용 workflow와 구분했다.
- 최신 `run_prices`를 보존하고 `Daily forward run` 하나를 복원했다.
  기본 dry-run이며 repository variable `FORWARD_DAILY_ENABLED=true`일 때만 실제 실행.
  17:17 KST/수동 실행에 한정하며 기존 주간·월간 승인 변수는 사용하지 않는다.
- 저장 가격 옵션, 계좌별 주문/처리 표시/체결/평가 원자성, 실패 격리,
  PARTIAL 당일 재시도를 구현했다. 금융 계산기·가격 collector·T0 정책·DB 스키마는 유지.
- 폐기용 PostgreSQL 18.6 포함 CI 동일 백엔드 검사 **684 passed, 0 failed, 0 skipped**.
  기존 가격 전용 계약 검사는 collector 격리 + 일간 전용 승인까지 확장했고,
  PARTIAL을 success로 기대하던 로컬 테스트는 가격 도착 후 같은 슬롯 완료까지 검증한다.
- 운영 DB/기존 앱/예약/백업은 변경하지 않았다. 푸시·병합·배포·실제 운용 실행 없음.
- 상세 실행 승인·검증·복구 한계: [ACTIONS_STORED_FORWARD.md](ACTIONS_STORED_FORWARD.md).

## 2026-10-06: 미설정 참가자 교수 시연용 one-off bootstrap

- `MinchoLover/robo`의 `release/public-operation` / PR #3 병합 커밋
  `6c9ecf38690e2eb3c303027140ddc01c164e8982`에서 별도
  `feat/demo-unready-bootstrap` worktree로 작업했다. 원래 체크아웃·앱·DB·예약은 보존했다.
- `scripts/bootstrap_unready_portfolios.py`: 활성 cohort의 실제 daily READY 판정을
  재사용한다. 기존 READY/판단/선택 구성/테마 선택/초안/운용 기록은 건너뛴다.
  15명 roster와 명시한 cohort를 확인하고 최대 10명만 결정적으로 배정한다.
- 실제 Frontier 점·기존 onboarding preview/complete 및 enrollment 저장 함수를
  사용한다. CLI에 직접 DB 삽입은 없다. dry-run은 읽기 전용이며 `--apply`만 저장한다.
  새 schema, migration, API endpoint, T0 예약, 주문·체결·NAV 생성은 없다.
- 폐기용 SQLite 및 PostgreSQL **18.6**: 신규 검증 **20개 통과**.
  5명 전체 기존 행 보존 → 10개 실제 첫 판단 → 15/15 READY, 서로 다른 테마 조합과
  세 위험대, dry-run 무쓰기, 재실행 무변경, 기존 초안·테마 선택 보호,
  첫 workspace 준비, 부분 실패 rollback/재개, 두 DB commit 실패의 대조 필요 상태를 검증했다.
- 최종 코드 기준 기존 CI 백엔드 명령
  `python -m pytest tests --ignore=tests/backup -q`: **702 passed, 2 failed, 0 skipped**.
  실패는 `tests/forward/test_inception.py::test4_launch_sets_inception` 및
  `test5_double_launch_fails`: 고정 가격의 마지막 날짜 `2026-09-14`가 현재 날짜의
  신선도 검사에 걸린다. 수정 전 `6c9ecf3`를 별도 복사한 환경에서도 같은 두 실패를
  재현했다. 이번 작업은 기존 날짜 의존 테스트를 수정·삭제·skip하지 않았다.
  프론트 변경이 없어 프론트 빌드·브라우저 검증은 대상이 아니다.
- 운영 DB에는 dry-run/apply 모두 실행하지 않았다. 사용자가 제공한 운영 5/15는
  원격 재조회 결과가 아니다. 실제 DB에 초안/기존 설정이 남아 있으면 해당 사람은
  보존되므로 자동으로 15/15를 보장하지 않는다. 운영 계획 확인과 별도 적용이 남아 있다.
- 두 DB의 분산 transaction은 만들지 않았다. 운용 판단 commit 후 인증 commit
  실패는 저장된 판단 ID와 `requires_reconciliation`을 보고한다. 다음 실행에서
  덮어쓰지 않고 건너뛴다. 강제 종료를 포함한 이 구간은 대조 후 별도 복구가 필요하다.
- 운영 DB·기존 앱·예약·Actions 승인 변수·백업 PR #12·배포 설정을 변경하지 않았다.
  GitHub 푸시·PR·병합·배포·운영 실행 없음.
- 사용법과 제한: [BOOTSTRAP_UNREADY_PORTFOLIOS.md](BOOTSTRAP_UNREADY_PORTFOLIOS.md).

## 2026-10-06: bootstrap release 반영 검증

사용자가 원래 bootstrap 커밋 `41e209c`의 `release/public-operation` 반영을 승인했다.
위 초기 로컬 검증의 실패 2개는 운영 신선도 기준이나 assertion을 바꾸지 않고,
해당 launch 테스트 가격 fixture만 현재 날짜까지의 10개 평일로 수정해 해결했다.
원래 bootstrap 구현 커밋은 보존하고 이 테스트/운영 안내 수정을 별도 커밋으로 남긴다.

최종 로컬 CI 동일 백엔드: **704 passed, 0 failed, 0 skipped** (폐기용 PostgreSQL 18.6 포함).
시작 회귀 파일은 **11 passed**. GitHub PR에서는 백엔드/프론트 CI도 확인한다.
Render 내부 환경변수로 활성 cohort를 읽고 dry-run만 실행하는 정확한 명령과
Free 플랜 제약, 빌드 갱신·시작 migration의 별도 영향은 bootstrap 문서에 기록했다.
운영 secret 로컬 복사, Render 배포, 운영 dry-run/apply, 승인 변수·T0·예약 변경은 하지 않았다.

## 2026-10-06: 수동 bootstrap Actions workflow

- PR #4의 release 병합 `8033c17`에서 별도 `feat/bootstrap-unready-actions` worktree로
  작업했다. 기존 bootstrap 서비스·daily/weekly/monthly·백업 workflow는 변경하지 않았다.
- `bootstrap_unready_portfolios.yml`은 `workflow_dispatch` 전용이며
  `release/public-operation`에서만 job을 허용한다. 기본 `apply=false`는 `--dry-run`,
  `apply=true`와 `APPLY_UNREADY_PORTFOLIOS` 확인값이 함께 있을 때만 `--apply`이다.
  활성 cohort는 기존 읽기 전용 `read_cohort()`로 조회하고 `--max-new 10`을 전달한다.
- 기존 인증/운용 Secrets 이름만 사용하며 원시 오류·URL을 출력하지 않는다.
  forward 작업과 같은 `forward-jobs` concurrency를 사용하고 실행 중 작업을 취소하지 않는다.
  migration 및 Render/Actions 신규 환경 설정·승인 변수 변경은 없다.
- 실제 workflow heredoc을 폐기용 stub 서비스로 실행한 신규 테스트 **14 passed**:
  모드 전달, 확인 없는 apply의 조회 전 차단, 잘못된 설정, cohort 누락,
  서비스 실패/비정상 결과의 실패 처리, 자격값 미출력을 확인했다.
- 기존 CI 동일 명령 `python -m pytest tests --ignore=tests/backup -q`:
  **718 passed, 0 failed, 0 skipped**, 폐기용 PostgreSQL **18.6** 포함.
  기존 bootstrap dry-run 무쓰기/15명 준비 회귀도 포함한다. 프론트 코드는 변경하지 않았다.
- 운영 dry-run/apply를 dispatch하지 않았다. GitHub Secrets의 **이름 존재만** 확인했고,
  실제 대상의 Render 일치 여부·운영 READY 수는 이번 테스트로 확인하지 않았다.
  사용법은 [BOOTSTRAP_UNREADY_PORTFOLIOS.md](BOOTSTRAP_UNREADY_PORTFOLIOS.md)의 Actions 절을 따른다.

## 2026-10-11 — Enable the shared forward start through Actions

The production cohort was READY 15/15 but had no shared T0; daily valuation was
still a dry run because `FORWARD_DAILY_ENABLED` was unset. Prices were collecting
successfully while trades, holdings and NAV remained empty.

`daily-forward` now accepts an optional `competition_start_date` on a manual
production-branch dispatch. A non-empty date on a non-dry-run dispatch invokes the
existing atomic `competition.schedule_start` command after the price collector's
DB identity checks. It validates readiness, initial capital, pending orders and
empty operating history. Scheduled runs, blank input and dry runs never schedule
a start. Date input is passed through an environment variable and quoted shell
argument. Existing immutable-start and future-KST-date rules remain in force.

Activation procedure: dispatch a future shared date, verify AWAITING_T0 and all
15 captured decisions, set `FORWARD_DAILY_ENABLED=true`, then dispatch normally
and verify a retryable COMPETITION_WAIT before T0. First fills/NAV require actual
post-T0 prices. No backfill or synthetic performance is introduced. Weekly and
monthly trading remain separately gated. Render/Vercel application deployment
is not required for this workflow-only change.

## Archived historical performance (2026-10-11)

The production collector already contained 110 observations for Oct 2–9.
External-source reconciliation found 30 differences: FX on Oct 2 and Oct 9,
plus fourteen unhedged asset conversions on each date. Independent refetch
with a wider date window confirmed the FX values. A compare-and-swap,
price-only transaction corrected these and preserved old/new values in
`PRICE_HISTORY_RECONCILED`; it refused to run if operating NAV or trades existed.
This is a source reconciliation, not proof of why Yahoo revised a value.
Ordinary collection remains append-only and never silently rewrites used prices.

The latest fifteen confirmed decisions were exported read-only, with no login
credentials, and evaluated in a separate marked SQLite replay ledger using
`create_orders`, `execute_pending`, and `valuate` under the existing local
replay scope. Six evaluation dates (Oct 2, 5, 6, 7, 8, 9), 30 accounts,
275 simulated fills, 1,650 holding rows and 180 NAV rows reconciled.
Initial buy-and-hold uses existing transaction costs and the existing
last-observed-price valuation rule. Every asset's price date is retained.
Current decisions postdate the replay start: these are counterfactual results,
not contemporaneous decisions or forward observations.

Fifteen `HISTORICAL_REPLAY_ARCHIVED` events store separate result payloads.
No historical fills/holdings/NAV were inserted into the operating ledger,
and no shared start was scheduled. The new authenticated read endpoint
`/api/v1/me/performance/history` verifies both the account and decision owner.
The dashboard shows an independent historical graph with a collapsed date/value
and methodology table. It never splices the archive into live returns, rankings,
or decision review observations. A subsequent configuration change is labeled.
No migrations or new secrets are required. Archives are optional; absent data
produces no preview. Removing the UI/API restores the prior presentation while
retaining the audit events.

Evidence, source comparisons, original exports, the one-off replay driver and
repair SQL are stored outside Git in the task workspace under
`work/price-history-repair-20261011/`. Do not commit account-level exports.
Validation includes owner isolation, anonymous rejection, unchanged live ledger,
archived-configuration labeling, price collection and replay regression tests,
frontend tests and production build.


### Prototype performance presentation — 2026-10-12

The saved historical performance card now uses “모의운용 성과” and a report-derived baseline date. Calculation details retain retrospective provenance, decision confirmation date, costs, and market price dates. This is a presentation-only change: no collection timestamps, archived results, live NAV, ranking calculations, or shared-start policy are changed.


### Saved simulation ledger details — 2026-10-12

The dashboard now defaults to the saved simulation when forward performance is absent, with explicit archive/forward selection. Saved holdings, cash, valuation snapshots, orders and fills use the existing LedgerHistory component. Historical order times are labeled simulation times. No forward rebalance recommendations or future dates are fabricated.

Existing immutable replay backups are exported with `ledger_read_service.ledger` in read-only mode, restricted to each participant's personal account, and appended as a new HISTORICAL_REPLAY_ARCHIVED revision including ledger details. Cohort-wide replay context is excluded. Guarded SQL requires exact parent archive, owner/decision/weights match, and conflict-free event IDs; no live orders, holdings, trades, NAV, start date or old events are updated. Fifteen personal accounts: 90 valuations, 155 orders, 155 fills and 930 daily holding rows. Every NAV agrees with cash plus holdings and its existing chart point.

### 2026-10-12: saved simulation cohort comparison
- Ranking now supports explicit `archive` / `forward` and `auto` sources. Auto uses saved simulations only while fewer than two participants have comparable forward returns.
- Match the owner's archive run, price-source checksum, period and execution assumptions; validate every archive's decision ownership. Reuse recorded-NAV report calculation and existing common-window ranking, themes, ties and risk-quality gates.
- Public responses contain normalized peer series and aggregate metrics only. Saved balances, orders, holdings and decision identifiers remain private. No ledger writes or changes to common start / daily-forward configuration.
- Dashboard links retain the selected source; users can switch independently to automatic operation.
- Verification: 22 relevant backend tests and 90 frontend tests passed. Tests cover source isolation, common-period rebasing, missing CORE, drawdown, cohort mismatch and public-response privacy.

## 2026-10-12 — opt-in dark dashboard preview

- Added `/dashboard?design=dark`, a single-page dark dashboard preview. Default routes retain their existing presentation.
- Reuses authenticated historical performance, forward performance, and ledger read APIs. Server-returned NAV/returns are unchanged; no database, collection, execution, or rebalance code changes.
- Saved simulation and forward records remain separate. Source dates and retrospective calculation provenance remain available in disclosures. Missing forward records remain empty.
- Large performance chart, actual holding mix, balance/cash summary, and links to existing portfolio/ranking/review and detailed records.
- 95 frontend tests and production build passed. Authenticated preview verified against the same deployed account values: NAV 99,099,642 KRW, return -0.85%, CORE -0.90%, cash 100,000 KRW, 6 archived evaluations and 11 mock trades. Source switching, empty forward state, and expanded ledger checked in browser. Desktop (1325px) and mobile (390px) have no horizontal overflow; mobile menu contrast corrected. Production deployment is intentionally deferred for design review.

### 2026-10-12 — unified dark workspace preview
- Extended the approved dashboard design to shared navigation, auth, setup, portfolio, performance/comparison, review, account and admin surfaces using central dark semantic tokens.
- Kept all API/mutation and financial calculation contracts intact. Dashboard overview links to existing detailed analysis with `view=details`; common/demo views remain routed to their existing implementations.
- Added a distinct administrator navigation group and direct judgment/strategy navigation. Replaced light chart axes and tooltip surfaces with readable dark presentation colors.
- Frontend regression suite: 95/95 pass. Production frontend build: pass. Browser QA will be appended after preview verification. Preview branch only; no production promotion or DB writes.
- Scope/decisions: docs/DARK_REDESIGN.md.

### Unified workspace — verification and final polish
- 100 frontend tests across 22 files passed; production build passed. Added route coverage for default overview, explicit details, performance, common comparison and period links.
- Authenticated preview checked with the existing participant account: login, dashboard overview/detail, risk slider (changed then restored without saving), themes, confirmation, portfolio, ranking filter, review, weekly opinions and account. Existing account metrics agreed across overview/detail; no portfolio confirmation, opinion submission or ledger write was performed.
- Narrow 390px viewport: menu navigation, portfolio and theme layouts verified without document overflow. Corrected summary number wrapping. Desktop checks at 1280px+.
- Standard-user access to admin tracking remained denied. Corrected the header badge to depend on the actual admin role instead of URL. Privileged administrator data screens were not browser-validated because no administrator session was available; existing internal tracking regression tests passed.
- Review now emphasizes saved estimates and collapses provenance/calculation detail. Strategy catalog now has an explicit selection state backed by the real catalog, plus loading/empty states. Weekly opinion labels are Korean; original selection limits and submission behavior are preserved.
- Only frontend presentation, route preservation, tests and documentation changed. Preview branch/Draft PR only; production and database untouched.

### Restore cumulative return contribution — 2026-10-12
The compact overview omitted the previous contribution chart, and the saved-simulation detail branch returned before rendering it. Restore the existing contribution visualization on the overview and saved detail view, with asset-group/individual-asset toggles. The authenticated history read response derives a performance report from the owner's immutable saved ledger through the existing `archive_report` / `calculate_report` calculator; no frontend P&L estimate, new price, ledger write or forward/archive mixing is introduced. The forward view reuses its existing server report.
Validation: 5 relevant backend tests pass, covering ownership, no live NAV/trade writes, unchanged archive payload, trade cash flow, costs and per-date reconciliation. 102 frontend tests pass, including source switching and group/asset presentation. Production build passes. Deployment/browser evidence is recorded separately after rollout.

### Chart tooltip contrast — 2026-10-12
The shared contribution/performance tooltip retained a translucent white background while dark-mode text tokens made its contents nearly invisible. Use an opaque dark surface, stronger border and readable label/value colors; slightly increase desktop/mobile type sizes. Presentation-only CSS; financial values and chart interaction remain unchanged. Verify existing frontend tests/build and the actual hovered production tooltip after rollout.

### 2026-10-13: strategy composition comparison and delayed daily valuation

Production had no leader/export marker wiring. Added an authenticated research comparison endpoint, reused portfolio_stats and weekly Ledoit-Wolf covariance on real observed adjusted closes for the supplied 10/1 leader target and 9/3 export post-fill composition. 44 observed stock/ETF histories, common 97 weekly returns (2024-11-08–2026-09-11); no Korean-equity return proxy, synthetic coordinates, interpolation, trading or account writes. Snapshot dates, holdings, annualization, cash/risk-free assumptions and differing historical/BL return bases remain visible. Setup, confirmation and saved portfolio use the same contract; whole-chart comparison and Frontier focus preserve exact coordinates.

The 38287688560 scheduled collector completed successfully but its delayed valuation started at 02:58 KST during US hours and failed in the legacy refresh guard. Stored-price valuation does not fetch bars, so only that path no longer uses the wall-clock collection guard. Live-refresh guard, completed-session provider, effective-date rules, jobs/transactions and duplicate prevention remain unchanged. Runtime regression exercises delayed open-market valuation, zero refresh, repeat idempotency and continued refusal of live-refresh during open hours.

Read-only Neon SQL audit: 10/12 four prices stored, zero duplicate asset/date keys, zero operating NAV/trades. Last daily attempts remain START_NOT_SCHEDULED (15/15 ready, shared T0 null). Do not claim valuation is operationally active until a separately scheduled shared start and a new recorded evaluation are observed.

Validation: backend 701 passed / 61 skipped (Postgres integration unavailable locally), frontend 103 passed; production build passed. Production source comparison and deployments are recorded in the task evidence outside the repository.

### 2026-10-14 — presentation Frontier visibility

Use one full-width chart and default to Frontier focus: all nine basic assets, the curve and Base/Personalized markers remain visible. Whole comparison adds the leader/export historical estimates on the same axes; returning to focus excludes only those two research markers and their detail cards. Both modes preserve exact server coordinates and portfolio selection. Historical versus BL return bases remain disclosed during whole comparison.

Increase axis and asset-label type sizes, reserve left-axis space, allow labels above or below crowded points, and keep the legend outside the SVG. The risk-selection summary follows its content height instead of stretching into an empty column. No optimizer, API, account, stored price, decision or execution changes.

Validation: 103 frontend tests and the production build pass. Final layout checked in an isolated SQLite fixture: all nine labels are inside the chart and do not overlap; risk changes update the selected metrics, whole/focus toggles preserve selection, and the theme/review flow retains both Base/Personalized markers. Portfolio confirmation was also verified in this fixture before the presentation-only refinements. No production test writes.

### 2026-10-14 — provisional V8 backtest comparison

Add an isolated authenticated V8 comparison read endpoint and a comparison-only marker on the existing shared chart. Reuse portfolio_stats and weekly Ledoit-Wolf covariance/52 annualization on the supplied unchanged USD equity curve, matched to the existing 97-week window (2024-11-08–2026-09-11). Plot weekly arithmetic return 43.7011498075%, volatility 21.2648879466%, Sharpe 1.9140072550 at the existing 3% risk-free assumption. Do not substitute full-history CAGR 49.24% or the reported 19.63% volatility. V8's scalar covariance is calculated independently so existing stock covariance, strategy points, Frontier and optimizer inputs remain unchanged.

Source: v8_ma_mdd_us_curve.csv, 943 USD observations (2023-01-03–2026-10-06), SHA256 efa3bd2f0bb1b8d830f60e18d4dd0efdf5e969c7520b32ad99b419d8dde54f65. Tooltip and details disclose USD, PROVISIONAL, unverified backtest status, matched period and non-CAGR arithmetic return. Cash flows/cost accounting in the source backtest remain unverified. Missing/invalid V8 data exposes its own 503 without affecting the original two-strategy endpoint. No DB/ledger writes or optimization/confirmation eligibility are added.

Validation: 26 relevant Python tests and 104 frontend tests pass; production build passes. Independent standard-library weekly aggregation matches the server metrics; tests cover source hash, malformed/missing-week rejection, authentication, V8 failure isolation, and unchanged original strategy/selected portfolio coordinates. Actual isolated local API-to-browser rendering and the provisional tooltip were verified. Production deployment is not included in this implementation step.

### 2026-10-14 — leader/export comparison point tooltips

Reuse the existing V8 comparison tooltip for all research markers. Leader/export hover, click and keyboard focus display the original server return, volatility, Sharpe and inherited common period. Describe them as historical stock/weight composition estimates, not actual operation; retain the distinct USD/PROVISIONAL description for V8. No new validation status, return proxy, currency conversion, coordinate, financial calculation or API/DB change.

Validation: 104 frontend tests and the production build pass. Coverage verifies tooltip values and server-period inheritance, hover/click/keyboard dismissal, unchanged point/portfolio coordinates, and continued V8 status isolation. Deployment and actual-browser evidence are recorded in the task workspace after rollout.


### 2026-10-24 — daily operation evidence and decision verification

Continue open PR #20 on its existing branch and worktree. Latest collector run
40063536709 stored 16 prices; latest valuation stage 39961497998 still reports
START_NOT_SCHEDULED / READY 15/15 with no orders, fills or NAV. Process success is
not operation completion. No operating start, deployment or production writes.

Reuse the existing collection, account transaction, execution, NAV and job registry.
Count persisted NAV rather than incomplete valuation attempts. Keep explicit
incomplete legacy successes retryable, retain unknown legacy success locks, and
preserve successful-slot deduplication. The verification API exposes allowlisted
execution/valuation states, checks persisted normal NAV, and retains outcome evidence
across duplicate skips. Frontend uses the server state rather than success=complete.

Preserve fixture/replay lineage in existing NAV events; copied replay state and
replaced synthetic prices cannot become forward performance. Original decisions
and missing historical estimates stay immutable; read requests never run trading.
The existing paired-date return engine and owner checks remain in place.

Contract, trade-offs, acceptance cases and remaining operating conditions:
docs/FRONTIER_DECISION_VERIFICATION.md. No new tables, services or backup changes.
Validation uses disposable local SQLite/PostgreSQL plus existing CI. Final measured
results are recorded in that contract and PR #20.

Final validation: 772 backend tests passed, zero skipped, with isolated PostgreSQL
14.19 and SQLite; 93 focused provenance/engine/replay tests passed; 111 frontend
tests and the production build/type checks passed. PostgreSQL LIKE pattern binding
was corrected after the new provenance test exposed it. Generated migration/parity
reports, covariance cache and Next environment declarations were restored and are
excluded from the change. No production DB was used.


### 2026-10-24 — frontend operation readiness and decision review completion

Continue PR #20 from 1a1edf6; its two CI runs completed successfully (backend and
frontend). Preserve the existing dark dashboard, Frontier and three-section panel.
Add safe reason_code to disambiguate an unspecified shared start from awaiting T0.
Dashboard empty states consume existing owner-scoped decision queries; readiness,
job date and NAV counts are server evidence. NAV_COMPLETE also requires the completion
flag, while actual.status controls paired-period performance. No GET runs operation.

Keep prior data visible on refresh failure and provide retry. Link the selected
decision's review back to its panel, filter its history, and restore keyboard focus
to the exact point/legend trigger. Current model and historical strategy comparisons
stay separate from saved forecasts. No replacement of missing Personalized values.

Validation: 123 frontend tests, explicit tsc --noEmit, production build, 25 verification
API tests and 2 actual-API Playwright scenarios passed. The browser flow covers login,
Base/Personalized selection, KEEP and ADJUST reasons, unchanged original, cache refresh,
desktop/mobile and failure recovery. Only disposable local SQLite fixtures were used.
The synthetic NAV success case remains UNAVAILABLE as actual performance. Screenshots,
exact reproduction and source limitations are in docs/FRONTIER_DECISION_VERIFICATION.md.
No operating start, deployment, production DB, backup workflow or sources/ changes.


### 2026-10-24 — production verification and decision date consistency

After PR #20 rollout, an authenticated production account showed the new waiting
status, zero forward NAV, separate archived results, both saved Frontier panels,
and Escape focus restoration correctly. The chart caption truncated confirmed_at
to its UTC date while the detail panel showed Korea time, producing different dates
for the same decision near midnight. Use Asia/Seoul explicitly in that caption,
matching the existing panel; date-only effective/price dates remain unchanged.
Extend the existing UTC-to-next-Korean-day interaction regression. No financial
values, account records, operating start or scheduler configuration are changed.

Validation: 123 frontend tests and production build/type checking passed.
