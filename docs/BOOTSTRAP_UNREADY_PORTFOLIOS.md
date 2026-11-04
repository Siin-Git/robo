# 교수 시연용 미설정 참가자 초기화 (one-off)

`scripts/bootstrap_unready_portfolios.py`는 준비 상태가 부족한 **현재 활성 cohort의 이미 가입한 사용자**만 검토한다.
현재 서비스의 Frontier/preview/complete, 최초 계좌 준비 및 enrollment 저장 함수를 재사용한다.
운영 DB에서 실행하지 않았다. 사용자 제공 상태 `READY 5 / required 15`는 이 작업에서 원격 재조회하지 않았다.

## 안전 조건

- `--dry-run` 또는 `--apply` 중 하나를 명시해야 한다. 모드가 없거나 둘 다 있으면 거부한다.
- 15개의 서로 다른 등록 사용자/참가자, `--expected-cohort` 일치, 최대 신규 10명만 허용한다.
- 실제 daily 엔진의 `competition.read_cohort/readiness`로 READY를 판정한다.
- READY와 기존 decision/선택 구성/테마 선택/비CORE 목표/운용 기록은 보존한다. 미확정 초안과 reset 이력도 건너뛴다.
  계좌 등록 시 생기는 기본 CORE 목표는 미설정 상태로 취급하며 삭제하거나 덮어쓰지 않는다.
- 진행 중인 공동 시작 예약이 있고 미완료 참가자가 남아 있으면 별도 검토가 필요하다.
- dry-run은 두 DB 모두 읽기 전용 transaction, SQLite CLI는 추가로 `mode=ro`로 연다.
  스키마 생성·마이그레이션·가격 수집·cache 재생성·ID 할당을 수행하지 않는다.
- 실행은 기존 `DATABASE_URL` 인증 DB와 `CAPSTONE_DESIGN_DATABASE_URL` 운용 DB를 사용한다.
  PostgreSQL에는 `DATABASE_BACKEND=postgres`, `APP_PROFILE=local`, `CAPSTONE_DEMO=1` 필요.
  두 DB가 같은 URL 대상이면 거부한다. 서로 다른 호스트 별칭이 실제로 같은 DB를
  가리키는 경우까지 URL 비교만으로 증명하지는 못하므로 대상 식별은 실행 전 별도로 확인한다.
  URL·비밀번호를 CLI 인자로 받거나 출력하지 않는다. 오류는 타입/단계만 출력한다.

## 결정적 배정과 저장

현재 첫 설정 화면의 기본 위험도 표시 기준(안정형 <6%, 중립형 6~8%, 공격형 >=10%)에서
실제 Frontier 점을 선택한다. 중립-공격형 구간은 이번 세 가지 배정에 사용하지 않는다.
전체 슬롯 번호 순서로 위험도를 순환 배정하므로 일부 성공 후 재실행해도 같은 roster/catalog의 배정이 이동하지 않는다.
인증/운용 DB 양쪽에서 활성·ticker 있는 기존 실행 가능 테마를 정렬한 뒤 단일/2개 조합을 배정한다.
필요한 고유 조합 수가 부족하면 실패한다. 미합의 주도주/수출 전략은 기존 서비스가 차단한다.
가격과 모형 데이터가 부족한 예상 지표는 기존 preview의 null을 그대로 보존한다.

이 설정은 사용자 직접 선택이 아닌 **교수 시연용 관리자 배정**이다. reason에
`PROFESSOR_DEMO_BOOTSTRAP_V1`, 슬롯과 기본 위험도를 저장하고 슬롯 configuration에도 시연 출처를 남긴다.
현재 시각과 기존 효력일 계산을 사용한다. 월별 기본값과 기존 저장된 주기 선호는 보존한다.
새 판단은 첫 버전이며 실제 apply 시 UUID가 할당된다. dry-run의 `decision_id=null`은 미생성 상태이고
가상의 저장 완료 ID가 아니다. 계획에 비중/예상 지표/예정 효력일, 결과에 실제 판단 ID와 READY 수를 출력한다.

초기 계좌 준비는 기존 API의 `ensure_design_identity`, 판단 저장은 `onboarding_service.complete`,
인증 슬롯 확정은 `enrollment_service.confirm_forward_design`에서 기존 enrollment 저장 함수를 사용한다.
마지막 함수는 HTTP API로 공개되지 않는 one-off 서비스 진입점이다. 기존 enrollment의 고정
시연 scenario를 배정하지 않고 실제 onboarding preview를 보존한다. 정상 사용자 API의 동작은 유지한다.

## 실행과 복구

운영 secret은 비공개 환경으로 주입한다. 활성 cohort ID는 인증 DB의
`forward_state.key=demo_active_cohort` 값과 기존 readiness 응답을 읽기 대조한다.
운영 실행 전 일관된 두 DB 백업·대상 식별·출력 계획과 기존 5명 보존을 검토한다.

```sh
python scripts/bootstrap_unready_portfolios.py --dry-run --expected-cohort COHORT_ID
# dry-run 검토 후 별도로 승인한 경우에만:
python scripts/bootstrap_unready_portfolios.py --apply --expected-cohort COHORT_ID
```

참가자별 슬롯/개인 계좌 잠금 후 기존 설정을 재확인한다. 기존 함수를 통해 계좌 준비와 판단을 저장하고,
운용 DB commit 다음 인증 슬롯 commit 순으로 READY를 노출한다. 실패하면 그 지점에서 중단하고
이미 성공한 사람은 보존한다. 정상적인 재실행은 기존 설정을 건너뛰며 중간 서비스 실패도 rollback 후 재시도 가능하다.

두 DB에 분산 transaction을 추가하지 않았다. 운용 commit 이후 인증 commit 실패·프로세스 강제 종료는
판단은 남고 슬롯은 미확정일 수 있다. 인증 commit 오류 결과에는 이미 저장된
`persisted_decision_id`와 `requires_reconciliation=true`를 출력한다. 프로세스 강제 종료 또는 다음 실행의
`EXISTING_DECISION_PRESERVED`를 확인하고 **대조 후 별도 복구**한다. 판단 삭제/재생성이나 자동 슬롯 정정을 하지 않는다.
최종 상태가 INCOMPLETE/FAILED이면 15/15 완료로 취급하지 않는다.

T0 예약, forward 활성화 변수, 배치·주문·체결·NAV·가격·과거 기록·백업 workflow·Vercel/Render 설정은 변경하지 않는다.
15/15 READY는 운용 시작이나 성과 생성의 증거가 아니다.

## GitHub Actions 수동 실행 (Render Free 대안)

Actions의 **Bootstrap unready portfolios**에서 **Run workflow**를 선택한다.
브랜치는 `release/public-operation`, `apply`는 기본 **false**, `confirmation`은
빈칸으로 유지하면 **dry-run만** 실행한다. 활성 cohort는 읽기 전용 `read_cohort()`로
자동 조회하고 `--expected-cohort`에 전달하며, `--max-new 10`을 고정한다.
계획과 실제 READY 수를 검토한 뒤 별도 승인한 경우에만 `apply=true`와 정확한
`confirmation=APPLY_UNREADY_PORTFOLIOS`를 함께 입력한다. 확인이 없으면 DB 조회 전 거부한다.

필요한 저장소 Secrets는 기존 `DATABASE_URL`(인증),
`CAPSTONE_DESIGN_DATABASE_URL`(운용)이다. **GitHub의 대상이 Render의 대상과 같은지**
소유자가 비공개로 확인해야 하며, 값은 입력 옵션·명령행·로그에 넣지 않는다.
프로필은 workflow가 `APP_PROFILE=local`, `CAPSTONE_DEMO=1`,
`DATABASE_BACKEND=postgres`로 지정한다. 수동 dispatch 외의 자동 실행은 없고,
다른 브랜치를 선택하면 job은 실행되지 않는다. `FORWARD_DAILY_ENABLED`나
`FORWARD_TRADING_ENABLED`의 변경·활성화는 필요하지 않으며 이 workflow가 변경하지 않는다.

daily/weekly/monthly forward와 동일한 `forward-jobs` concurrency 그룹을 사용하고
실행 중 작업을 취소하지 않는다. 이 보호는 **같은 저장소의 Actions 작업 간** 적용되며,
별도 로컬 배치/API 요청까지 잠그지는 않는다. 기존 참가자별 재확인·슬롯/계좌 잠금은 유지한다.
이 작업에서는 workflow의 구현·격리 테스트만 수행하며 운영 dry-run/apply를 dispatch하지 않는다.

## Render에서 secret을 복사하지 않고 dry-run

운영 URL은 로컬로 복사하지 않는다. 아래 명령은 스크립트가 포함된 Render 빌드의
저장소 루트에서 실행한다. 활성 cohort를 읽기 전용으로 확인하고 기존 CLI의 dry-run만
호출한다. 환경값은 검사만 하며 변경하거나 출력하지 않는다.

```sh
python - <<'PY'
import os
import sys
from pathlib import Path

if not Path("scripts/bootstrap_unready_portfolios.py").is_file():
    sys.exit("SCRIPT_NOT_FOUND")
expected = {"APP_PROFILE": "local", "CAPSTONE_DEMO": "1", "DATABASE_BACKEND": "postgres"}
if any(os.environ.get(k) != v for k, v in expected.items()):
    sys.exit("ENVIRONMENT_MISMATCH")
if any(not os.environ.get(k) for k in ("DATABASE_URL", "CAPSTONE_DESIGN_DATABASE_URL")):
    sys.exit("DB_ENVIRONMENT_MISSING")
try:
    from src.forward.competition import read_cohort
    from scripts.bootstrap_unready_portfolios import main
    cohort = read_cohort()
    if not cohort:
        sys.exit("ACTIVE_COHORT_REQUIRED")
    result = main(["--dry-run", "--expected-cohort", cohort["cohort_id"], "--max-new", "10"])
except Exception as error:
    print("FAILED:", type(error).__name__)
    sys.exit(1)
sys.exit(result)
PY
```

[Render Free](https://render.com/docs/free)는 Shell과 One-Off Job을 지원하지 않는다.
실제 서비스의 플랜과 실행 권한은 아직 확인하지 않았다. 유료 서비스의
[One-Off Job](https://render.com/docs/one-off-jobs)은 기반 서비스의 최신 성공 빌드와
환경변수를 그대로 사용한다. GitHub release 병합만으로 기존 Render 이미지가 바뀌지는 않는다.
일반 재배포의 시작 명령에는 마이그레이션이 있으므로, dry-run의 무쓰기 검증과
빌드/재시작의 운영 영향은 별도로 확인한다. 배포·플랜·시작 명령은 이 작업에서 변경하지 않는다.

## 로컬 검증

검증은 SQLite와 PostgreSQL 18.6의 폐기용 인증/운용 DB에서 수행한다.
기존 5명 보존, 신규 10명 고유 배정/15 READY, dry-run 전체 행 불변, 최초 workspace 생성,
초안/기존 판단 건너뜀, 중단/재개, 재실행, 인증 commit 실패, 잘못된 대상과 cache, 읽기 전용 위반을 검사한다.
최종 명령/결과는 `docs/INTEGRATION_EXECUTION.md`에 기록한다. 운영 실행·15명 실계정의 계획은 미검증이다.
