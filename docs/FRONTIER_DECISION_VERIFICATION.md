# Frontier 투자 판단 검증

## 범위와 완료 기준

기존 Next.js `/portfolio`의 Base 또는 Personalized 점을 선택하면 옆에
당시 판단, 동일 기간 계좌 성과, 당시 가정의 재검토를 표시한다.
다크 대시보드와 기존 자산 구성·현재 모형/전략 비교를 보존한다.
운영 환경의 주문 생성·거래 실행·배포와 신규 저장 인프라는 범위에 포함하지 않는다.
2026-10-24 후속 작업은 기존 예약 엔진의 상태·재시도와 검증 API 연결까지 포함한다.

## 데이터와 결정

- 원본 저장소: `MinchoLover/robo`, 기준 `release/public-operation@8bee054`.
- `GET /api/v1/me/portfolio/summary`에 `decision_id`를 추가했다.
  최신 판단의 `selection_id`와 현재 선택이 일치할 때만 연결한다.
- `GET /api/v1/me/decisions/{decision_id}/verification`은 인증 사용자 본인의
  설계 DB만 조회한다. 다른 사용자의 판단은 404, 비로그인은 401이다.
- Personalized 예상값·비중은 append-only `portfolio_decisions`에서 읽는다.
  Base 예상값은 새 판단부터 기존 provenance JSON에 함께 저장한다.
  기존 판단은 연결된 과거 `base_portfolio_selections`에 있는 값을 읽으며,
  없는 과거 예상값을 현재 모형으로 소급 생성하지 않는다.
- 당시 곡선은 기존 스냅샷의 좌표만 공개한다. 관리자용 진단 전체나 검토
  내용은 공개하지 않는다. 곡선이 없으면 미확보를 표시한다. 현재 모형의
  자산·전략 비교는 별도 접힌 상세에 유지한다.
- Personalized 기대수익률이 없을 때 Base 기대수익률로 대체하던 경로를
  제거했다. 좌표 두 값이 모두 확보된 점만 그린다.
- 계좌 성과는 판단 효력일부터 후속 판단 효력일 전까지, 한국시간 오늘까지
  기록된 NAV로 제한한다. 두 계좌의 같은 날짜만 사용하고 정상 NAV 두 시점
  이상일 때 기존 `calculate_report`로 기간 수익률을 산출한다.
- `NAV_INCOMPLETE`, stale, 비양수/비유한 NAV, CORE 버전 불일치를 제외한다.
  과거 가격 재생 메타데이터나 합성 테스트 가격이 있으면 실적을 제공하지 않는다.
  가격 관측·모형 추정·샘플 수익률로 NAV를 대체하지 않는다.
- 표의 기준은 사용자 Base가 아닌 별도 CORE 계좌다. 공통 첫 평가일·종료일,
  관측 수, 양쪽 시작/종료 NAV를 명시한다. 거래비용은 저장된 NAV에 반영된
  그대로이며, 기존 폐쇄형 모의계좌의 외부 입출금 없음 가정을 따른다.
- 연간 예상 기간이 끝나지 않거나 시작일을 확보하지 못하면 검증 진행 중이다.
  기간을 확보해도 재검토 필요로 표시하며 기대수익률 적중 여부는 판정하지 않는다.
  사용자 KEEP/ADJUST 기록은 사용자 재검토 근거로만 표시한다.
- 새 테이블·마이그레이션·외부 서비스 없이 기존 판단과 선택 기록을 재사용한다.
  판단 원본, 과거 NAV, 목표 비중과 주문은 조회 과정에서 변경하지 않는다.

## 검증

- `npm ci --no-audit --no-fund`로 기존 잠금 파일에 맞춰 설치.
- `npm test -- --reporter=dot`: 프런트엔드 108개 통과.
- `npm run build`: Next.js production 빌드 및 타입/린트 검사 통과.
- `.venv/bin/python -m pytest tests/api tests/forward/test_performance_report.py -q`:
  213개 통과, 1개 건너뜀. PostgreSQL 전용 테스트는 `TEST_DATABASE_URL` 미설정으로 건너뛴다.
- 최종 변경 후 판단/검증 API 11개와 프런트 108개, production 빌드를 다시 통과했다.
- 원본 Frontier 50개 점의 기대수익률과 저장된 BL 자산별 기대수익률의
  가중합 차이 최대 0. 자산별 기대수익률도 일치한다.
- 회귀 범위: 소유권, 불변 원본, 현재 모형 변경과 과거 자료의 분리,
  공통 평가일, 미래/효력일 이전/후속 판단 구간 제외, 불완전 NAV,
  한 시점/CORE 자료 부족, 합성·재생 제외, 누락 예상값 대체 금지,
  점 클릭/키보드/닫기·포커스 복원/조회 재시도.

브라우저 검토는 별도 로컬 SQLite 계정으로 진행했다. 저장소의 과거 가격은
예상 위험 계산에만 사용하고 NAV·주문·체결은 생성하지 않았다.
넓은 화면의 우측 배치, 390px 모바일의 가로 넘침 없음, Base/Personalized 전환,
Escape 닫기와 점으로 포커스 복원, 기존 9개 자산 비교를 확인했다.
운영 계좌의 실제 자료 보유 여부를 이 로컬 검토로 확인했다고 주장하지 않는다.

## AI 작업과 검토

Codex가 기존 서비스·모델·화면을 추적하고 API, 패널과 회귀 테스트를 작성했다.
자동 테스트와 로컬 브라우저에서 검증하며 운영 DB를 테스트 대상으로 사용하지 않았다.


## 공유 검토 대화 반영 및 자동 갱신 보완 (2026-10-23)

참조: https://chatgpt.com/s/cx_6adadcfea2208191b08c2bc682a63fa4

- 최초 판단 보존, 예상/실제 구분, 기록된 근거와 검토 History 연결을 반영했다.
  기존 관리자 전용 자산 추적/Revision은 그대로 두고 공개 패널에 노출하지 않는다.
- 기존 daily-forward 예약의 가격 수집과 NAV 평가를 재사용한다. 별도 스케줄러,
  거래 실행 경로, 데이터 저장소를 추가하지 않았다.
- 포트폴리오/판단 증거는 화면이 활성화된 동안 60초마다 재조회한다.
  새 NAV와 사용자 검토 기록은 다음 조회에서 반영된다. 최초 스냅샷은 변경하지 않는다.
  갱신 실패 시 이전 자료와 경고를 함께 표시하고 재조회할 수 있다.
- 전체 일일 평가 작업의 상태·날짜만 읽는다. 작업 성공과 개별 계좌 NAV 확보를
  별개로 표시하고, 내부 오류·작업 통계는 사용자 응답에 포함하지 않는다.
- 동일 decision_id의 기존 검토 화면으로 연결한다. 기존 KEEP/ADJUST 저장 성공 후
  검증 캐시를 무효화한다. 새 저장 기능이나 자동 매매 의사결정은 추가하지 않는다.
- 저장된 변동성 산출 근거, 비중 미확보를 명시한다. Base에는 Personalized 테마
  산출 근거를 붙이지 않는다. 잘못된 숫자/불완전 좌표와 미기록 CORE 버전은
  현재 모형으로 보완하지 않는다.
- GitHub 읽기 확인: FORWARD_EXECUTOR=actions, FORWARD_DAILY_ENABLED=true.
  최근 예약 5회 성공, 2026-10-22 실행 39790231486의 가격 수집/일일 평가 단계 성공.
  이것만으로 모든 계좌에 충분한 실적이 있음을 주장하지 않는다. 설정 변경/수동 운용
  실행/운영 배포는 하지 않았다.
- 최종 로컬 검증: API 및 성과 계산 215 passed, 1 skipped (PostgreSQL 접속 미설정),
  프런트 110 passed, Next production build 통과. 자동 재조회 시 새 NAV·검토 근거·
  만기 상태 반영과 원본 보존, 실패 작업의 비공개 진단 제외를 회귀 검증했다.
- 로컬 브라우저에서 패널 → 동일 판단 검토 화면 → 포트폴리오 복귀 확인.
  별도 검토 DB에 운용 NAV/주문/체결을 생성하지 않았다.


## 자동 운용 백엔드 보완 (2026-10-24)

### 확인된 운영 상태

PR #20은 OPEN, 작업/원격 HEAD는 `7109caa`, 운영 브랜치는 `8bee054`에서
시작했다. 기존 작업 경로는 깨끗했으며 해당 브랜치를 이어서 수정했다.

- 최신 수집 실행 [40063536709](https://github.com/MinchoLover/robo/actions/runs/40063536709):
  2026-10-24, `status=OK`, 가격 16건 추가. 이 실행은 일일 운용 단계 대상이 아니다.
- 최근 일일 운용 단계 [39961497998](https://github.com/MinchoLover/robo/actions/runs/39961497998):
  2026-10-23, `START_NOT_SCHEDULED; READY 15/15; no orders, fills or NAV`.
- 따라서 GitHub 작업의 성공은 평가 완료를 뜻하지 않는다. 10월 22일 단계 성공을
  기록한 위 과거 메모도 프로세스 종료 결과이며 운용 활성화 증거가 아니다.
  이번 확인은 로그 읽기이며 운영 DB 변경·예약 dispatch·공동 시작일 지정은 하지 않았다.

### 연결과 상태 계약

기존 `daily_forward.yml`의 완료 가격 수집 → `run_daily --use-stored-prices` →
계좌별 주문/체결/`valuate` 트랜잭션 → 동일 설계 DB의 `nav_daily`, `scheduled_jobs`
→ 소유권 확인된 검증 GET 경로를 유지한다. 별도 예약 작업이나 DB를 만들지 않는다.

기존 API `GET /api/v1/me/decisions/{decision_id}/verification`의 `valuation_job`을
다음 형태로 확장했다. 아래는 시작일 미지정 기록을 해석한 **응답 형태 예시**이며
운영 API에 이 변경을 배포했다는 의미가 아니다.

```json
{
  "valuation_job": {
    "status": "success",
    "latest_attempt_status": "success",
    "scope": "ALL_ACCOUNTS",
    "scheduled_for": "2026-10-23",
    "completed_at": "2026-10-23T13:29:51+00:00",
    "state": "START_WAIT",
    "message": "공동 운용 시작일 미지정",
    "reason_code": "START_NOT_SCHEDULED",
    "execution_succeeded": true,
    "valuation_completed": false,
    "valuated": 0,
    "ready": 15,
    "required": 15,
    "retryable": true
  }
}
```

| `state` | 의미 |
| --- | --- |
| `RUNNING` | 실행 중 |
| `START_WAIT` | 시작일 미지정 또는 T0 도달 전 |
| `PARTICIPANTS_NOT_READY` | 참가자 준비 부족 |
| `OPERATION_WAIT` | 나머지 운용 게이트 대기, 원문 사유는 비공개 |
| `PRICE_WAIT` | 체결/평가용 가격 미확보 또는 stale NAV |
| `EVALUATION_FAILED` | 실패 종료 또는 실패 통계, 재시도 필요 |
| `NO_NAV` | NAV 저장 0건 |
| `PARTIAL` | 일부 평가·검사 미완료 또는 정상 NAV 저장 확인 불충족 |
| `NAV_COMPLETE` | PASS, 양수 저장 건수, 미완료 신호 없음, 해당 날짜 정상 NAV 저장 확인 |
| `UNKNOWN` | 완료를 입증할 기록 부족 |

- 작업 기록 자체가 없으면 `valuation_job=null`이다. `status`는 증거가 있는 작업의
  원래 상태이며 `execution_succeeded`도 그 실행 결과만 뜻한다. 프런트는
  `message`/`state`와 `valuation_completed`를 사용한다. 구형 API의 `success`만
  받은 경우에도 프런트는 “작업 성공 · 평가 완료 여부 미확인”으로 표시한다.
- 가장 최근 날짜에서 빈 중복 건너뜀 기록을 넘겨 원래 평가 결과를 보여주고,
  `latest_attempt_status`로 마지막 시도의 건너뜀 여부를 보존한다.
- `valuated`는 NAV 저장 계좌 수(정상+stale), `successful_accounts` 내부 통계는
  정상이며 가격 대기가 없는 계좌 수다. 구형 통계에 계좌별 결과가 있으면
  `NAV_INCOMPLETE` 시도를 저장 수에 넣지 않는다. 값이 없으면 null이다.
- `NAV_COMPLETE`는 전체 배치의 저장 상태이며 본인 판단의 성과 확보와 별개다.
  `COMPETITION_WAIT`, `PARTIAL`, `valuated=0`이면 프로세스가 성공했어도 완료가 아니다.
- 전체 `stats_json`, 원문 오류, 계좌별 결과/오류/ID, 연결 정보는 공개하지 않는다.
  공개 숫자와 고정 메시지만 허용한다.

기존 응답 본문은 다음 계약을 유지한다.

| 필드 | 실제 타입과 사용 |
| --- | --- |
| `decision_id`, `version`, `confirmed_at`, `effective_date` | 확정 원본 식별자, 정수 버전, ISO 시각/날짜 |
| `reason`, `superseded_effective_date` | 원래 이유 및 후속 효력일, 없으면 null |
| `original.base`, `original.personalized` | `{expected_return: number|null, volatility: number|null, weights: Record<string,number>}` |
| `original.frontier` | `{version: string|null, points: [{frontier_id, expected_return, volatility}]}` |
| `original.return_basis`, `risk_basis`, `price_data_as_of` | 당시 산출 근거·자료 기준일 또는 null |
| `actual` | 아래 공통 기간 성과 객체 |
| `review` | `{status: IN_PROGRESS|REVIEW_REQUIRED, horizon_end: string|null, automatic_verdict: false, basis: string, choice: {action, reason, recorded_at}|null}` |
| `read_only` | 항상 true |

`actual`은 `{status: AVAILABLE|UNAVAILABLE, reason: string|null, start: string|null,
end: string|null, observations: number, excluded_rows: number,
personalized_return: number|null, core_return: number|null, difference_pp: number|null,
personalized_nav: {start:number,end:number}|null, core_nav: {start:number,end:number}|null}`이다.
반환 수익률과 `difference_pp`는 기존 엔진의 **소수 단위**다. 예를 들어 `.01` 차이는
프런트에서 `1.00%p`로 표시한다. NAV 단위는 KRW이며 미확보를 0으로 대체하지 않는다.

동일 CORE 버전·공통 날짜의 정상 NAV가 최소 두 시점 있어야 계산한다. 최초 예상
수익률·변동성·비중·확정일은 변경하지 않고, 누락된 과거 값을 소급 생성하지 않는다.
새 NAV/KEEP·ADJUST가 커밋되면 다음 GET에서 반영하며 연간 예상과 단기 실현 차이를
적중 판정에 쓰지 않는다. GET은 가격 수집·주문·체결·평가를 호출하지 않는다.

### 출처와 재시도 정책

- 신규 `NAV_CALCULATED` 이벤트의 기존 JSON에 `data_kind`를 추가한다.
  `FORWARD_SIMULATION`, `TEST_FIXTURE`, `HISTORICAL_REPLAY`를 구분한다.
  과거 이벤트는 고치지 않는다. 원장 이름을 바꾸어도 `replay_run_id` 상태가 있으면
  재생으로 차단한다. 대소문자를 포함한 기존 `synthetic*` 가격도 차단한다.
- 합성/재생 NAV 이력이 있는 두 계좌는 가격표가 갱신돼도 실제 이후 운용 성과로
  승격하지 않는다. 기존 출처 정보가 전혀 없는 과거 NAV는 새로 추정하지 않고 기존
  저장소 출처 검사와 정상 NAV 조건을 적용한다. 출처 불명의 과거 데이터를 실제
  운용 DB에 가져와 실적으로 사용해서는 안 된다.
- SQLite `BEGIN IMMEDIATE`, PostgreSQL slot advisory lock과 계좌 트랜잭션을
  그대로 재사용한다. 새 성공은 같은 슬롯의 반복 실행을 차단하고 건너뜀을 기록한다.
- 실패·가격 부족·시작 대기·PARTIAL은 다음 시도에서 같은 슬롯 재실행이 가능하다.
  구형 `success`라도 명시적인 미완료 통계가 있으면 슬롯을 소비하지 않는다.
  통계가 없는 구형 성공은 안전하게 잠금을 유지하며 자동 거래 재실행을 추정하지 않는다.
- 진행 중 작업은 기존 6시간 stale 기준 이전까지 잠기며 실패 기록은 보존한다.
  실패 계좌는 기존 트랜잭션으로 롤백되고 다른 계좌의 성공은 유지된다.
  완료 계좌 재처리 시 주문/체결 중복이 생기지 않는 기존 규칙을 검증했다.
- 자동 재시도 루프를 추가하지 않는다. 기존 일일 운용 예약은 08:17 UTC 단계이며,
  다음 예약 또는 별도 승인된 동일 슬롯 재시도가 필요하다. `retryable`은 즉시
  재실행 예약이 걸렸다는 의미가 아니다.

### 남은 운영 조건

이 PR은 코드 완성과 격리 검증 단계다. 운영 활성화에는 별도 승인된 병합/배포 후
참가자 준비 상태·동일 초기 자본·대기 주문 적합성 확인, 명시적인 미래 공동 시작일,
그 이후 체결 가능한 가격과 예약 실행이 필요하다. 실제 평가 완료는 새 작업의
정상 NAV 저장을 확인해야 한다. 판단 성과 비교는 본인과 CORE 공통 정상 NAV가
최소 두 시점 쌓인 뒤 제공된다. 이번 작업에서 시작일·운영 DB·예약 변수는 바꾸지 않는다.

### 이번 검증

테스트는 `/private/tmp`의 SQLite와 `127.0.0.1:55432`의 폐기 가능한
PostgreSQL 14.19 인스턴스/테스트 DB를 사용한다. 운영 DB 주소는 테스트에 사용하지 않는다.
기존 CI의 PostgreSQL 서비스도 같은 회귀 파일을 실행한다.

- 핵심 테스트 107 passed (SQLite/PostgreSQL 포함).
- 프런트 111 passed, Next.js production build 및 타입 검사 통과.
- 최종 전체 백엔드: `python -m pytest tests --ignore=tests/backup -q` → **772 passed**, 0 skipped (221.25초).
- 출처·엔진·재생·검증 API 추가 회귀: **93 passed**. PostgreSQL LIKE 패턴 바인딩 오류를 발견해 매개변수 바인딩으로 수정한 뒤 재검증했다.
- 기존 CI는 PostgreSQL 18 서비스를 사용한다. 이번 로컬 전체 테스트도 PostgreSQL 관련 검증을 건너뛰지 않았다.
- 경고 745건은 기존 pandas 등의 deprecation 경고이며 테스트 실패가 아니다.
- UI 변경은 상태 문구만이므로 해당 컴포넌트와 전체 프런트 테스트/빌드로 검증했으며 이번 단계에서 운영 브라우저 거래나 별도 E2E 실행은 하지 않았다.
- 기존 lockfile로 `npm ci --no-audit --no-fund`, Python `pip check` 통과.
  별도 Python lint/typecheck 명령은 저장소에 없다.
- Codex가 기존 코드와 최신 로그를 추적하여 수정하고 명령 실행 결과로 검증했다.
  `sources/`, 백업 PR, 운영 배포 파일/변수는 변경하지 않았다.


## 프런트 연결 및 실제 API 브라우저 검증 (2026-10-24)

### 구현 범위와 결정

기존 PR #20 / `1a1edf6`을 이어 작업했다. 별도 앱·목업·디자인 시스템을 추가하지
않고 기존 다크 대시보드, Frontier, 오른쪽 검증 패널, 검토 페이지를 유지했다.
완료 기준은 로그인 → 저장된 판단 선택 → 근거 확인 → 유지/조정 이유 저장 →
같은 판단으로 복귀하여 최신 기록 확인이다. 운영 배포·시작일 변경은 제외한다.

- 패널의 세 항목(당시 판단, 동일 기간 계좌 성과, 당시 가정의 재검토)을 유지한다.
  저장 좌표와 현재 모형/과거 전략 비교를 분리하고 누락 Personalized는 대체하지 않는다.
- `valuation_job.state`와 `valuation_completed`를 함께 해석한다.
  `NAV_COMPLETE`라도 완료 플래그가 true가 아니면 정상 저장 완료로 표시하지 않는다.
  구형 `success`만 있는 응답은 평가 완료 여부 미확인으로 남긴다.
  개별 판단의 성과 확보는 별도 `actual.status`로 판단한다.
- `START_WAIT`만으로 시작일 미지정을 추측할 수 없으므로 API에 작은 호환 확장인
  `reason_code: START_NOT_SCHEDULED | AWAITING_T0 | PARTICIPANTS_NOT_READY | null`을
  추가했다. 허용되지 않은 내부 사유는 null로 남긴다. 미지정과 지정일 도달 전을
  각각 명시하고 준비 인원·작업 기준일·NAV 저장 수는 서버 값만 표시한다.
  구형 API에 사유 코드가 없으면 일반적인 시작 대기로 표시한다.
- 대시보드 개요와 상세의 빈 상태는 기존 `decisions`, `decision-verification`
  React Query 키와 인증된 읽기 API를 재사용한다. 새 실행 API는 호출하지 않는다.
  화면 조회와 서버 운용 실행이 다르다는 설명을 표시한다.
- 포트폴리오 요약·판단 증거·대시보드의 갱신 실패는 이전 자료를 유지하면서
  경고와 재조회 버튼을 표시한다. 첫 조회 실패는 성공 자료가 있는 것처럼 보이지 않는다.
  조회 간격은 기존 60초이며 백그라운드 주기 조회는 비활성화한다.
- 검토 페이지는 선택한 판단의 KEEP/ADJUST 이력만 보여주고 같은 `decision_id`의
  패널로 돌아가는 링크를 제공한다. 저장 시 기존 검증 캐시를 무효화한다.
  ADJUST는 기존 재설계 페이지를 열며 새 확정 전에는 최초 판단을 덮어쓰지 않는다.
- Enter/Space, 클릭, Escape/닫기, 점/범례의 실제 선택 요소로 포커스 복원을 확인했다.
  데스크톱 오른쪽·모바일 아래쪽 배치를 유지한다. 비활성 본문 이동 링크를 클리핑해
  긴 모바일 화면 캡처에서도 떠 있는 링크가 나타나지 않도록 했다.

### 검증 결과와 화면 증거

**아래 모든 화면은 격리 테스트 환경이다.** 계정, 판단 이유, 준비 인원 15/15,
작업 날짜, NAV 수치 모두 테스트 DB의 기록이며 운영 실적·운영 활성화 증거가 아니다.
성공 사례는 화면/저장 흐름 성공과 NAV 저장 상태 확인이다. 합성 NAV는 API에서
`actual.status=UNAVAILABLE`이며 운영 성과로 표시하지 않는다.

| 확인 항목 | 화면 |
| --- | --- |
| 공동 시작일 미지정·서버 준비 인원·최근 작업일 | [대시보드](evidence/decision-verification-ui/dashboard-wait-desktop.png) |
| 저장된 Frontier 점과 우측 세 항목 패널 | [데스크톱 패널](evidence/decision-verification-ui/verification-desktop.png) |
| 390px 배치·가로 넘침 없음·최신 조정 이유 | [모바일 패널](evidence/decision-verification-ui/verification-mobile.png) |
| 동일 판단의 유지 이유 저장 | [검토 저장](evidence/decision-verification-ui/review-saved-desktop.png) |
| 정상 NAV 저장 작업과 합성 실적 제외의 분리 | [합성 자료 제외](evidence/decision-verification-ui/synthetic-nav-excluded-mobile.png) |
| 이전 자료 유지·갱신 실패·다시 조회 | [통신 실패](evidence/decision-verification-ui/refresh-failure-desktop.png) |

- `npm test`: **123 passed** (25 files).
- `npx tsc --noEmit`: **통과**. 기존 Testing Library 테스트 5곳의 지원되지 않는
  `getByRole({exact:true})` 옵션도 제거했다. 문자열 name 매칭은 이미 정확 일치다.
- `npm run build`: **통과**, 실제 브라우저 테스트도 이 production 빌드로 실행했다.
- `python -m pytest tests/api/test_decision_verification.py -q`: **25 passed**.
- `E2E_DECISION_VERIFICATION=1 ... npx playwright test --config playwright.operations.config.ts`:
  **2 passed (10.2초)**. 실제 FastAPI/SQLite와 Next 동일 출처 프록시를 사용한다.
  성공 응답을 모킹하지 않는다. 실패/로딩 테스트에만 네트워크 중단/지연과 브라우저
  타이머를 사용해 60초 조회 주기, 이전 자료 유지, 초기 오류, 재조회 복구를 확인했다.
- 브라우저에서 KEEP, ADJUST 이유 저장 후 같은 판단을 다시 읽고 최초 판단 객체가
  동일함을 검증했다. 이 구간 주문 0·체결 0·NAV 0·작업 1·판단 1은 변하지 않고
  사용자 선택만 0→2가 된다. 이후 명시적인 fixture 명령으로만 합성 NAV 4건과
  성공 작업 1건을 추가했고, 성과 미확보와 테스트 자료 경고를 확인했다.
- 앞선 `1a1edf6`의 push/PR CI 둘 다 backend/frontend **SUCCESS**를 확인했다.
  [push CI](https://github.com/MinchoLover/robo/actions/runs/40075557866),
  [PR CI](https://github.com/MinchoLover/robo/actions/runs/40075561165).
  기존 PG18 전체 검사는 통과했으며 이번 순수 사유 코드 변경은 API 회귀로 검증했다.

### 재현 방법

새 `/private/tmp` 경로를 사용한다. fixture 도구는 이미 있는 경로의 준비를 거부하며
표시된 marker가 없는 디렉터리에 NAV를 넣지 않는다. 계정 비밀번호 파일은 비공개
테스트 디렉터리에만 남기고 Git에 포함하지 않는다.

1. 저장소에서 `.venv/bin/python scripts/seed_verification_ui_fixture.py --directory /private/tmp/robo-verification-new` 실행.
2. `APP_PROFILE=local CAPSTONE_DEMO=1 CAPSTONE_MARKET_COMPARISON=1 DATABASE_BACKEND=sqlite DATABASE_URL='' CAPSTONE_DESIGN_DATABASE_URL='' CAPSTONE_DATA_DIR=/private/tmp/robo-verification-new AUTH_COOKIE_SECURE=false ALLOW_PUBLIC_REGISTRATION=false` 환경으로
   `.venv/bin/python -m uvicorn src.api.main:app --host 127.0.0.1 --port 8057` 실행.
3. `web`에서 `NEXT_PUBLIC_CAPSTONE_DEMO=1 NEXT_PUBLIC_LAB_MEETING=1 FASTAPI_INTERNAL_URL=http://127.0.0.1:8057 npm run build`, 같은 환경의 `npm run start -- --hostname 127.0.0.1 --port 3057` 실행.
4. `web`에서 `E2E_DECISION_VERIFICATION=1 E2E_BASE_URL=http://127.0.0.1:3057 E2E_OPERATIONS_DATA_DIR=/private/tmp/robo-verification-new npx playwright test --config playwright.operations.config.ts` 실행.

Codex가 구현·테스트를 수행하고 실제 화면 PNG를 확인했다. 운영 DB·공동 시작일·예약
설정·운영 배포는 변경하지 않았다. 테스트 환경은 운영 서버에 연결하지 않는다.
