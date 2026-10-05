# 저장 가격 기반 Daily forward: 로컬 검증 및 실행 승인

기준: MinchoLover/robo `release/public-operation` / `6f94193859abd629db025dd70c511f1ee323c3c1`.
작업: `fix/actions-stored-forward`, `/private/tmp/robo-actions-stored-forward-20261005`.
운영 DB·계정·T0·예약 실행·Render/Vercel·백업 PR #12는 변경하지 않았다. 푸시·병합·배포·운영 Actions 실행도 하지 않았다.

## 실제 workflow 버전 구분

사용자가 확인한 [37208198285](https://github.com/MinchoLover/robo/actions/runs/37208198285)는
2026-10-04 UTC의 `b6add63` 실행이다. 그 버전에는 `Daily forward run`이 있고,
`inputs.dry_run`에 따라 `run_daily --dry-run`을 사용했다. 이후 기본 브랜치의
`6f94193`에는 `run_prices` 단계만 있다. 최신 완료 세션 수집을 보존하고,
동일한 이름의 `Daily forward run` 하나를 복원했다. 실행 단계는 중복되지 않는다.

## 구현과 변경하지 않은 계산

- `python -m src.forward.run_daily --use-stored-prices`: `refresh_live`만 생략한다.
  옵션이 없으면 기존 가격 갱신을 그대로 수행한다. 이미 연결된 CLI를 다른 엔진으로 바꾸지 않았다.
- 이 옵션은 현재 완료 세션 collector의 정확한 세션 날짜·환율 정책을 유지하기 위해 필요하다.
  `refresh_live`를 다시 호출하면 별도의 수집/채움 정책을 적용할 수 있기 때문이다.
- 주문 계획, 체결 가격 선택, 비용, 수량·현금·보유 평가, NAV, 상대 10% 밴드의 계산 함수는 수정하지 않았다.
- READY/T0/account_gate 및 소급 체결 차단은 유지된다. 옵션이나 dispatch 날짜로 T0를 앞당기지 않는다.
- 평가일은 FX를 제외한 실제 저장 자산 가격의 마지막 날짜이며 실행 asof 이후 행은 사용하지 않는다.
  휴장이라고 당일 NAV를 임의로 만들지 않는다. 최초 체결 전에는 NAV anchor를 만들지 않는다.
- 최초 체결은 효력일/T0 이후 첫 저장 종가를 기다린다. 보유 평가의 기존 최근 가격 fallback과
  `stale_price_days=14`를 유지한다. 14일 초과는 가격 폐기가 아니라 기존 `STALE_PRICE` 표시다.

## 계좌별 원자성과 복구

`_account_transaction`은 계좌 행의 UPDATE 잠금(PostgreSQL row lock / SQLite writer lock)을
얻고, 기존 금융 함수의 내부 commit을 그 계좌 처리 종료까지 유예한다.
주문·판단 처리 이벤트·체결·상태 갱신·보유·NAV·감사 이벤트는 함께 commit하거나 rollback한다.
다른 호출자는 기존 금융 함수의 commit 동작을 그대로 유지한다.

- 같은 판단의 `DECISION_ORDER:<id>` 표시, 기존 pending 재사용, pending만 체결하는 규칙을 유지한다.
- CORE 최초 주문은 기존 주문 또는 체결 이력이 있으면 다시 생성하지 않는다.
- 예외 계좌는 rollback 후 `DAILY_ACCOUNT_FAILED` 이벤트에 account/stage/error class를 기록하고 다음 계좌로 진행한다.
  원시 예외 문자열·연결 URL·자격값은 계좌 오류 기록에 넣지 않는다.
- 예상된 가격/최초 체결 대기는 pending을 보존하고 당일 재시도를 허용한다.
- valuation의 예상되지 않은 `NAV_INCOMPLETE`도 해당 계좌의 실패로 처리한다.
- 미래 효력일의 재설계 pending은 아직 실행 대상이 아니므로 그것만으로 당일 완료를 막지 않는다.
- 성공 계좌는 유지하고 실패 계좌만 다음 시도에서 복구된다. 동일 날짜 재평가는 기존 키로 upsert한다.

## 결과와 scheduled_jobs

`stats_json.outcome`은 `SUCCESS / PARTIAL / FAILED`이며,
`account_results`, `account_errors`, `waiting_accounts`, `successful_accounts`, `retryable`을 저장한다.
기존 로컬 보고용 `status=PASS/FAIL/PARTIAL/COMPETITION_WAIT`는 호환성을 위해 유지한다.

| 결과 | exit code | scheduled_jobs.status | 같은 KST 날짜 재시도 |
|---|---:|---|---|
| 필수 작업·검사 완료 | 0 | success | 이미 완료로 skip |
| T0/가격 대기 또는 경고 PARTIAL | 0 | skipped, retryable=true | 허용 |
| 일부 계좌 오류 | 1 | failed, outcome=PARTIAL | 허용 |
| 성공 계좌 없이 오류 | 1 | failed, outcome=FAILED | 허용 |

새 migration이나 DB status enum은 필요 없다. skipped/failed 시에도 상세 stats를 보존한다.
재시도 가능은 자동으로 즉시 재시도한다는 뜻이 아니다. 예약 전체 운용은 17:17 한 번이며,
같은 날 재시도가 필요하면 승인 후 workflow_dispatch 또는 실패 실행 재실행을 사용한다.
진행 중인 다른 실행은 기존 job 선점에 의해 차단된다. 프로세스가 강제 종료되어 running이
남으면 기존 6시간 stale 정책을 따른다. --force/임의 scheduled-for/다른 job DB로 우회하지 않는다.

## workflow와 계정 소유자가 확인할 설정

가격 collector는 기존 07:30/09:17/17:17 KST, 대상 DB·revision 확인, read-only preflight 및
보고서 업로드를 유지한다. 같은 시각을 유지하면서 cron을 분리해 17:17 이벤트를 식별했다.
전체 Daily 단계는 17:17 이벤트 또는 workflow_dispatch에서만 실행되며, 기본 명령은:

```bash
python -m src.forward.run_daily --use-stored-prices --dry-run
```

일간 전용 repository variable이 정확히 `true`이고 수동 요청이 dry_run이 아닐 때만:

```bash
python -m src.forward.run_daily --use-stored-prices
```

| 위치 | 이름 | 값/확인 방법 |
|---|---|---|
| GitHub Actions Variables | FORWARD_EXECUTOR | actions; 실행 주체는 하나만 사용 |
| GitHub Actions Variables | FORWARD_DAILY_ENABLED | 미설정/false이면 Daily 엔진은 dry-run. 검토 완료 뒤 true로 별도 승인 |
| GitHub Actions Variables | FORWARD_TRADING_ENABLED | 일간 승인에 사용하지 않음. 기존 주간·월간을 켤 계획이 없다면 미설정/false 유지 |
| GitHub Actions Secrets | DATABASE_URL | Render의 실제 인증 DB와 같은 Neon endpoint/branch/database를 비공개로 대조 |
| GitHub Actions Secrets | CAPSTONE_DESIGN_DATABASE_URL | Render가 조회하는 운용 DB와 동일한 대상인지 비공개로 대조 |
| Render | APP_PROFILE / CAPSTONE_DEMO / DATABASE_BACKEND / FORWARD_EXECUTOR | 기존 local / 1 / postgres / actions 유지. 이번 변경을 위한 새 Render 변수 없음 |

Variables/Secrets는 Repository Settings → Secrets and variables → Actions에서 설정한다.
값은 채팅·로그에 출력하지 않는다. `FORWARD_DAILY_ENABLED`는 Render 환경변수가 아니라
workflow 승인 변수다. 코드가 배포/기본 브랜치에 반영되기 전에는 설정만 바꿔도 이 구현이 실행되지 않는다.

실제 실행 전 필수 확인:
1. 기본 브랜치의 workflow와 API 배포 버전을 구분하고, 해당 수정이 실행될 커밋을 확인한다.
2. 두 secret의 연결 대상·운용 스키마·scheduled_jobs와 decision/account/user 연결을 확인한다.
   DB 이름만 같다는 것으로 같은 Neon branch라고 판단하지 않는다.
   읽기 preflight 성공은 쓰기 권한의 증거가 아니다. 운용 역할의 orders/trades/holdings_daily/nav_daily/
   counters/events/forward_state/scheduled_jobs 쓰기 권한과 schema 권한도 비공개로 확인한다.
3. 15명의 실제 확정/READY와 저장된 공동 T0를 확인한다. 이번 수정은 T0를 예약하지 않는다.
4. 기존 pending/체결/판단 처리 이벤트와 scheduled_jobs를 읽기 확인한다.
   구버전에서 PARTIAL이 success로 저장됐다면 같은 날짜는 기존 완료 선점에 의해 건너뛴다.
   과거 처리 표시·주문·job을 이 수정이 자동으로 삭제/정정하지 않는다. 이상 상태는 별도 검토한다.
5. 최신 가격 source·세션 날짜·환율 누락·첫 효력일 이후 가격을 확인한다.
6. 같은 원격 DB를 쓰는 노트북/다른 예약 실행이 없는지 확인한다. GitHub concurrency는 외부 실행자를 막지 않는다.
7. dry-run은 연결·수량 preflight이며, T0 충족/가격 적합/체결 성공을 시뮬레이션한 증거가 아니다.
   폐기용 PostgreSQL 검증과 운영 실행 결과는 별개다.

## 검증

최종 실행 결과는 아래 및 `docs/INTEGRATION_EXECUTION.md`에 기록한다.
검증용 합성 가격과 고정 날짜는 테스트 fixture/폐기용 DB에만 사용했다.

- Python 3.11 / 폐기용 PostgreSQL 18.6에서 CI 동일 명령 `python -m pytest tests --ignore=tests/backup -q`:
  **684 passed, 0 failed, 0 skipped**. 기존 의존성 deprecation 경고 23개.
- 새 테스트는 SQLite와 PostgreSQL 양쪽에서 15명 개인·CORE 30계좌, 기존 체결/미체결 혼합,
  pending 재사용, 주문 처리 표시 직전/체결 직후/평가 직후/SQL 오류 주입, 실패 후 재개,
  다음 평가일 연결, 같은 계좌 동시 실행, T0 전 차단, 외부 refresh 미호출, dry-run 무쓰기,
  승인 변수/수동 dry-run 쉘 분기를 검증한다.
- 전체 실행에서 NAV=현금+보유평가액, 재실행 거래/비용/행 수 불변 및 초기 주문 재생성 방지를 확인했다.
- Python 문법·workflow YAML/Bash 문법·diff 공백 검사 통과.
- 백업 테스트 제외는 기존 `.github/workflows/ci.yml`의 동일 범위다. PR #12 코드는 건드리지 않았다.
- 프론트/API 응답/화면은 변경하지 않아 프론트 빌드나 브라우저 검증을 이번에 다시 수행하지 않았다.
- 운영 역할의 실제 쓰기, 운영 계좌 15명의 READY/T0, Render와 Actions의 실제 DB 동일성,
  원격 CI 및 승인 후 실제 운용 실행은 **미검증**이다. 운영 데이터로 체결 시험하지 않았다.
- 기존 3073/3099/3103 서버와 로컬 운용 DB·예약은 재시작하거나 변경하지 않았다.
- 검증 로그: `/private/tmp/robo-daily-pg-AGQMZB/backend-final.log`.

- 테스트 산출물을 기준 버전으로 복구한 뒤 변경 영역을 다시 실행: **57 passed, 0 failed, 0 skipped**.
  명령: `python -m pytest tests/forward/test_stored_daily.py tests/forward/test_price_only.py tests/forward/test_local_market_operation.py -q`.
  로그: `/private/tmp/robo-daily-pg-AGQMZB/focused-final.log`.
