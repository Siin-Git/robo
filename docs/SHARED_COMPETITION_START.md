# 15명 공동 운용 시작 제어

2026-10-04. 기준 `origin/release/public-operation`의 `b6add63`, 작업 브랜치
`feat/shared-competition-start`. 별도 `.work/competition-start`에서 작업한다.
코드·폐기용 DB 검증·로컬 커밋 범위이며 원격 반영과 실제 T0 예약은 수행하지 않는다.
기존 3073 앱, 인증/운용 데이터, 자동 적립 예약과 다른 체크아웃은 유지한다.

## 저장 구조와 상태

기존 인증 DB의 `DemoCohort`/`DemoSlot`과 `forward_state.demo_active_cohort`에서
참가자 명단을 읽는다. 인증 연결은 읽기 전용이다. 기존 prepared 참가자도 같은
명단에 포함하지만, 기본 목표나 준비 계정만으로 READY라고 간주하지 않는다.

READY는 활성 사용자·연결된 참가자·최종 확정된 slot(등록형 계정)·활성 personal/CORE
계좌와 해당 사용자/참가자/personal 계좌에 속한 불변 `PortfolioDecision`이 모두
확인되는 상태다. 기본 참가자 수는 기존 `COHORT_SIZE=15`이며 정확히 15명과
중복 없는 참가자 ID가 필요하다. 운영자가 전체 READY를 확인한 뒤 T0를 명시적으로 예약한다.
사용자별 기존 effective date는 보존하며 T0는 이 날짜들보다 이르면 안 된다.

운용 DB의 기존 `forward_state`에 다음 키를 한 트랜잭션으로 한 번만 저장한다.
새 테이블·마이그레이션은 없다. 기존 `value VARCHAR(256)` 제약을 지키도록
참가자 참조를 키별로 나눈다.

| 키 | 내용 |
| --- | --- |
| `competition_start` | cohort ID, 필수 인원, 공통 시작일, 한국시간 T0, 예약 시각 |
| `competition_member:<user_id>` | 사용자·참가자·personal/CORE 계좌·예약 당시 판단 ID |
| `forward_test_inception_at` | 모든 참가자에게 동일한 T0, 한국시간 00:00 |

READY/STARTED는 이 저장값, 현재 명단/확정 상태와 실제 한국시간으로 계산한다.
STARTED는 운용이 **허용됨**을 뜻하며 체결이나 NAV가 이미 생성됐다는 뜻은 아니다.
`DemoSlot.forward_started_at`에 미래 시각이나 가짜 체결 완료를 기록하지 않는다.
판단 스냅샷과 과거 판단은 변경하지 않는다. 최초 구성은 T0 예약 당시 판단 ID로
고정하고 이후 재설계 버전은 원래 확정·효력일 흐름대로 보존한다.

## 운영자의 확인·예약 명령

API 및 Actions와 **같은 인증/운용 대상**을 가리키는 기존 환경 설정을 비공개로
로드한 뒤 저장소 루트에서 실행한다. URL/비밀번호를 명령행에 입력하거나 로그에
출력하지 않는다. 필요한 기존 환경 이름은 `APP_PROFILE=local`, `CAPSTONE_DEMO=1`,
`DATABASE_BACKEND`, `DATABASE_URL`, `CAPSTONE_DESIGN_DATABASE_URL`이다.
SQLite에서는 기존 `CAPSTONE_DATA_DIR`의 두 DB를 사용한다.

```sh
# 명단, READY 인원, 예약 및 대기 사유 조회
python -m src.forward.competition

# 운영자가 합의한 미래 한국 날짜로 교체해서 한 번 예약
python -m src.forward.competition --start-date YYYY-MM-DD
```

새 T0는 현재 한국 날짜보다 뒤여야 한다. 당일 자정이나 과거로 소급해서 시작하지
않는다. 같은 cohort/날짜의 반복 예약은 기존 값을 반환하고 날짜 변경은 거부한다.
다음 상태에서는 데이터를 수정하지 않고 예약을 거부한다.

- 전체 READY 미충족, T0 이전에 효력이 발생하지 않는 최초 판단
- 기존 inception/최초 체결 상태, 해당 계좌의 기존 체결·holdings·NAV
- 계좌별 초기 가상 투자금이 다르거나 정상적인 양수가 아닌 경우
- 최초 판단/기존 CORE와 다른 pending 비중, 매도 주문, 중복 자산 주문, T0 이후 효력일

명단/계좌 변경, 계정 비활성화, 인증 조회 실패, 판단 참조 손상, inception 불일치도
실행을 차단한다. 예약 후 명단을 다시 확인하며 오래된 별도 cohort에 자동 적용하지 않는다.
기존 금액을 동일하게 검증할 뿐 금액을 변경하지 않는다. 진행 중 원장을 초기화하거나
충돌 주문을 임의 삭제하는 명령은 추가하지 않았다.

## 주문·체결·평가 차단 위치

- `competition.policy/account_gate`: 실제 한국 시각, 전체 READY, 공통 T0와 명단 검사.
  배치의 날짜 인자나 고정 시연 시계로 실제 시각 검사를 우회할 수 없다.
- `state.live_orders_blocked`: 기존 live 프로필 검사 앞에 공동 시작 검사를 적용한다.
  `APP_PROFILE=local`인 Actions도 차단된다.
- `run_daily._execute_daily`: 가격 갱신은 허용하되, 준비/예약/T0 대기 시 주문 루프·
  체결·평가를 전부 건너뛰고 `COMPETITION_WAIT`와 이유/READY 수를 기록한다.
- `execution.create_orders/execute_pending`, `ledger.valuate`: 직접 호출에도 같은
  검사와 T0 날짜 하한을 적용한다. T0 이전 날짜의 체결/holdings/NAV를 만들지 않는다.
- 주간/월간 배치도 같은 검사로 T0 전 최초 주문 생성 우회를 차단한다.
  기존 가격·위험 자료 갱신과 금융 계산식/리밸런싱 기준은 유지한다.
- `job_cli.finish_job/jobs.wait_job`: 대기는 기존 `skipped` 작업 이력으로 보존하여
  같은 날짜 재시도를 허용한다. 실행 중 잠금과 성공 작업의 중복 방지는 유지한다.

기존 pending 최초 주문은 ID·제출일·원래 효력일을 보존한다. 체결 가격 검색 시작만
`max(원래 효력일, T0)`로 제한한다. 호환되는 초기 pending은 재사용하므로 동일 자산
주문을 추가하지 않는다. 이 날짜 간 재사용은 최초 체결 전으로 제한하며 이후 주문의
기존 효력일별 중복 방지 규칙은 바꾸지 않는다. 충돌 pending은 보존하고 예약을 거부한다.

T0 이후에는 기존 가격 조회·비용·현금 조정·모의체결·holdings/NAV 엔진을 그대로
사용한다. T0 이전 가격만 있거나 시장이 휴장하면 주문은 대기하고 NAV는 생성되지 않는다.
이 대기는 `PARTIAL`로 표시하며 배치 오류나 가짜 성과로 채우지 않는다. T0는 공통
**운용 허용일**이다. 모든 종목이 그 날짜에 체결되는 보장은 없으며 실제 종가와 배치
실행이 필요하다. 새 CORE 최초 주문의 기존 생성 당일 효력 규칙은 유지하므로 T0 배치가
누락되면 최초 실제 체결일이 늦어질 수 있다. 과거 운용 기록 backfill은 수행하지 않는다.

## Actions 적용과 검증

기존 `.github/workflows/daily_forward.yml`은 `APP_PROFILE=local`, `CAPSTONE_DEMO=1`,
`DATABASE_BACKEND=postgres`, `FORWARD_EXECUTOR=actions`, 한국시간 설정과 두 DB secret으로
`python -m src.forward.run_daily`를 호출한다. 이 경로 자체에 검사했으므로 workflow의
금융 동작/예약 시각/secret/실행 주체를 변경하지 않았다. 기본 브랜치에서 예약 실행하므로
수정 코드가 해당 실행 브랜치에 반영돼야 실제 Actions에서 보호된다. 이 작업은 푸시·병합·
배포·운영 DB 변경·실제 workflow 실행을 하지 않았다.

폐기용 SQLite와 PostgreSQL 18에서 실제 확정 서비스를 사용해 2명 및 **15명 전체**를
자동 검증한다. 가격과 계정은 `SYNTHETIC_TEST`이며 실제 로컬/Neon 원장에 넣지 않는다.

- A만 확정/B 미확정 → 일간 및 직접 주문·체결·평가 호출에 체결/holdings/NAV 0건
- 전원 READY이나 미예약 → 차단; 예약 후 T0 이전 → 기존 pending 보존, 결과 0건
- 미래 job 날짜/가격이 있어도 실제 시각이 T0 전 → 차단
- T0 및 종가 도달 → 모든 personal/CORE의 기존 체결·holdings/NAV 생성, 회계 항등식 확인
- T0 시점에 오래된 가격만 존재 → 평가 대기, 다음 정상 CLI 실행에서 T0 종가로 체결
- 반복 실행/연결 재시작 → 저장값 유지와 체결·NAV 중복 없음
- 충돌 pending·기존 체결·초기 자금 불일치·명단 변경·인증 연결 실패 → 안전한 거부
- 예약 당시 판단 보존, 이후 판단 버전 유지, 초기 이후 기존 주문 규칙 유지
- 기다린 job의 같은 날짜 재시도, 실행 중 잠금, 완료 job의 중복 실행 방지

최종 전체 백엔드 **569 passed / 0 failed / 0 skipped** (Python 3.11.15,
폐기용 PostgreSQL 18 및 SQLite). 새 공동 시작 회귀는 24개이며 기존 15명
로그인/최종 확정/API·배치 같은 DB/재시작 검사도 전체 실행에 포함한다.
프론트 **71 passed (16 files)**, Next production build/타입 검사 통과.
UI 변경이 없어 이번에는 추가 브라우저 조작 검사를 수행하지 않았다.

검사 명령은 다음과 같다. 테스트 PG URL은 폐기용 DB만 가리켜야 한다.

```sh
python -m pytest tests --ignore=tests/backup -q -p no:cacheprovider
cd web
npm run test
npm run build
```

CI의 기존 PostgreSQL 테스트 환경 변수를 사용하므로 운영 secret 없이 재현할 수 있다.
`TEST_AUTH_DATABASE_URL`/`TEST_DESIGN_DATABASE_URL`이 없는 개발 환경에서 새 PG 변형만
미검증으로 skip되고, SQLite 검사는 계속 실행된다. 이번 로컬 검증에서는 모두 준비했다.

## 남은 적용 작업

운영자가 수정 코드를 검토·반영한 뒤 실제 인증 cohort/계좌 연결, 15명 READY,
충돌 pending 없음과 같은 초기 자금을 확인하고 미래 T0를 합의·예약해야 한다.
운영 DB에는 이번에 T0를 지정하지 않았다. 기존 3073 앱/스케줄러도 코드 전환하지 않았다.
실제 Actions 적용과 실제 시장 가격에 의한 공동 최초 체결은 미검증이다.
TIPS 가격, history/backfill, 랭킹/기여도, 알림/±10%p, 백업 PR #12 및 UI 개편은 범위 밖이다.
