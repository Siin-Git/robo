# 가입 → 생성 → 비교 시연 운영 안내

## 목적과 완료 기준

신규 참가자가 기존 인증으로 가입하고, 공통 CORE와 Theme 최대 2개를 확정한 뒤 같은 앱의 내 포트폴리오·성과 대시보드·참가자 비교로 이동한다. 기존 v1의 Theme 카드, 카테고리, 미리보기, 최종 비중 확인 UI를 재사용한다.

P0: 실제 인증 / 예약된 비교군 / 복원 가능한 설정 / 변경 불가능한 실험 구성과 비교 연결.
P1: 기존 NAV의 Race·Risk–Return·정렬별 순위·Theme 선택자 집계.
P2: 기존 Backend의 TE·IR·주간 수익만 노출. 새 금융 엔진, Sortino, 가상 Attribution 생성은 범위 밖이다.

## 실행과 1~2회 시연

프로젝트 `robo` 디렉터리에서 실행한다. 기존 `data/capstone_demo.db`와 `data/portfolio_design.db`는 보존한다. 모든 명령은 시연 모드의 별도 SQLite 파일에만 적용한다.

```bash
export APP_PROFILE=local CAPSTONE_DEMO=1 DATABASE_BACKEND=sqlite
.venv/bin/python -m src.local.seed_capstone

# --email은 실제로 가입할 새 이메일로 변경한다. 1개면 12+1, 2개면 11+2.
# 초대 파일은 저장소 밖에만 생성되며 파일 권한은 0600이다.
.venv/bin/python -m src.local.demo_cohort \
  --name professor-rehearsal-01 \
  --email presenter-one@example.com \
  --out /private/tmp/professor-rehearsal-01.json

.venv/bin/python scripts/start_demo.py --no-browser
```

1. 초대 파일을 발표자만 열어 해당 이메일의 초대 코드를 확인한다. 비밀번호는 가입 화면에서 직접 새로 입력한다. 코드·비밀번호를 Git, 회의 문서, 공개 채팅에 붙이지 않는다.
2. `http://127.0.0.1:3001/signup`에서 실제 가입한다. 기존 Argon2id 해시·서버 세션·쿠키·CSRF를 그대로 사용하며 기존 정책대로 자동 로그인한다.
3. 공통 CORE 구성과 근거를 확인한다. Theme 2개와 이유를 입력한다. 입력 후 **서버에 저장됨** 표시를 확인한다. 새로고침·재로그인하면 서버 초안으로 복원된다.
4. 예: 반도체+인공지능, 방산·항공우주+원자력·우라늄 등 ‘가상 시연 성과가 제공되는 조합’을 선택한다. 최종 비중·이유·성과의 성격을 확인하고 생성한다.
5. 내 포트폴리오 → 내 성과 대시보드 → 참여자 성과 비교 → Race/위험수익 지도/랭킹 → 상세 화면으로 이동한다.
6. 두 번째 독립 시연은 **새 이름과 새 이메일**로 준비 명령을 다시 실행한다. 기존 시연의 계정·설정·NAV는 삭제하거나 재연결하지 않는다. 활성 비교군만 명시적으로 변경된다. 같은 비교군에서 두 번 가입하려면 처음부터 `--email`을 두 개 지정한다. 첫 생성 후 12명, 두 번째 생성 후 13명이다.

서버 시작과 seed는 비교군을 준비하거나 사용자 설정을 초기화하지 않는다. 동일 이름의 준비 명령은 거절하며 초기화 대신 새로운 비교군을 추가한다. 기존 계정은 계속 로그인할 수 있고 본인의 원래 시연 보고서를 조회한다. 이전 비교군의 신규 계정도 저장한 구성을 유지하지만 현재 비교군 순위에는 포함되지 않는다.

## 메뉴와 데이터 경계

- 포트폴리오: 포트폴리오 설계 `/setup/portfolio`, 내 포트폴리오 `/portfolio`, 주간 투자 의견 `/views`, 기존 자유 설계 성과 `/performance`.
- 성과 비교: 성과 대시보드 `/dashboard`, 참여자 비교·랭킹 `/ranking`.
- 상세: `/participants/{participantId}`. 메뉴에 별도 버전·앱 선택을 두지 않는다.

인증과 확정 비교는 `capstone_demo.db`, 자유 설계는 기존 작업의 `portfolio_design.db`를 사용한다. 자유 설계 DB의 사용자 행은 비활성 참조이고 암호·세션을 복제하지 않는다. 로그인은 하나다. 로컬 실행기는 기존 `data/forward_local.db`가 있으면 `DESIGN_PRICE_SOURCE`로 지정해 가격 이력만 설계 DB에 최초 한 번 연결한다. 계정·NAV·보유·거래는 읽거나 복제하지 않는다. 기존 위험 계산 함수와 5Y weekly Ledoit-Wolf 규칙을 그대로 사용한다. 이미 있는 가격은 자동으로 덮어쓰지 않는다. 배포 환경에 이 공개 가격 자료가 없다면 예상 위험 지표는 데이터 없음으로 남는다. 실험의 최초 확정만 예약 슬롯에 연결하며 이후 자유 설계·주간 의견은 확정 구성과 성과를 수정하지 않는다. 자유 설계 저장 후에는 `/portfolio?workspace=design`에서 그 결과를 확인하고, 메뉴의 내 포트폴리오는 확정 실험 구성을 표시한다. 앱·버전 전환이 아닌 저장 대상의 구분이다.

추가된 두 테이블 `demo_cohorts`, `demo_slots`는 비교군 설정, 이메일에 묶인 초대 해시, user 연결, 초안, 확정 구성, 공개 시나리오 보고서 스냅샷, 확정 시각을 저장한다. 기존 테이블을 변형하거나 기존 계정을 이전하지 않는 작은 추가 구조다. 명시적 준비 CLI가 데모 DB에만 테이블을 추가하며 Production 마이그레이션은 실행하지 않는다.

가입 요청은 유효한 초대·예약 이메일이 있어야 통과한다. 정원은 계정 전체가 아닌 비교군의 슬롯이다. SQLite 데모 요청은 `BEGIN IMMEDIATE`로 직렬화하고, 조건부 UPDATE와 UNIQUE 제약으로 중복 가입·슬롯 배정을 막는다. 모든 저장이 같은 트랜잭션에서 성공해야 반영된다. 초기 확정은 기존 CSRF 검증에 더해 본인 슬롯과 미확정 상태를 검사한다. 같은 완료 요청은 기존 결과를 반환하고 다른 구성으로 재확정하면 409를 반환한다.

## 실제 정보와 가상 정보

| 구분 | 저장·표시 방식 |
| --- | --- |
| 실제 정보 | 회원 계정, 암호 해시, 세션, 예약 슬롯, 선택 CORE/Theme/이유, 서버 초안, 확정 시각, 현재 날짜의 목표 비중 |
| 가상 시연 | 기존 `seed_capstone`의 검증된 공개 NAV 시나리오. 2026-04-01~2026-09-11, 시작 NAV 100. 기존 수치는 변경하지 않음 |
| 시나리오 배정 | Theme 집합과 목표 비중이 모두 정확히 일치할 때만 공개 보고서를 불변 스냅샷으로 배정. `DEMO_SCENARIO_ASSIGNED`, 시나리오 ID, 신규 참가자 ID 표시 |
| 실제 Forward Test | 새 계정에 과거 NAV·보유·거래 기록을 복사하지 않음. `forward_started_at=null`, 실제 실행 시작 전 상태. 실제 엔진 실행을 이 작업에서 시작하지 않음 |
| 지원하지 않는 조합 | 구성·이유는 확정 가능. `FORWARD_PENDING`, `metrics=null`, 빈 series, 성과 집계 대기. 등록 인원에는 포함, 과거 전체 기간 순위에서는 제외 |
| 실제 적용 비중 | 시연에는 실제 보유 데이터가 없으므로 ‘고정 목표 구성’으로 표시. 실제 보유 비중으로 오인시키지 않음 |

공통 CORE의 근거는 `outputs/frozen/CORE_V0.3/metadata.json`의 `risk_anchor=neutral_60_40_volatility`, `primary_covariance=5Y weekly Ledoit-Wolf`, `target_volatility=0.08923641664549675`이다. 5%를 하드코딩하지 않는다. 약 8.92%는 목표 모형 위험 기준이고 실현 변동성 보장이 아니다.
Theme Budget·초기자금·초기 NAV·비용은 `config/forward_v0.yaml`을 사용한다. 가상 시나리오는 실제 위험 가드레일·거래 비용을 다시 계산한 엔진 산출물이 아니다. 실제 실행 위험 검증은 앞으로 연결해야 한다.

## Analytics와 API 계약

하나의 비교 보고서를 Dashboard / Ranking / Race / Detail에서 사용한다. 가격·금융 계산은 프론트에 구현하지 않는다.

| 기능 | 지원 단계·근거 |
| --- | --- |
| 누적 NAV, Return, Excess, MDD, Volatility, Sharpe | 1. 기존 comparison API / Backend `perf_metrics` 사용 |
| Race, Scatter, CORE marker, 상대 순위 | 2. `/comparison/analytics`로 기존 보고서를 묶어 노출. 새 NAV 생성 없음 |
| TE / IR | 2. 기존 Backend `tracking_ir` 결과 노출. 동일 NAV·기간 사용 |
| 기준 주간 Portfolio / CORE / Excess | 2. 기존 `perf_metrics`에 마지막 데이터 주간과 직전 평가일을 전달. 응답 `week_start`, `start`, `end`를 구분 |
| Theme 선택자 평균 | 2. 같은 기간의 성과가 있는 참가자의 동일 가중 산술평균. 두 Theme 선택자는 양쪽 포함. Theme 자체 수익률 아님 |
| Sortino | 3. 기존 비교 계산 결과 없음. 준비 중 표시 |
| Asset / Base / Theme Contribution, Top·Bottom Contributor | 3. Backend에 실제 장부 기반 성과 보고 기능은 있으나 현재 가상 NAV와 대응하는 장부는 없음. 별도 기존 forward CSV를 혼합하지 않음 |

`GET /me/experiment`: 본인 설정 상태, 활성 비교군·정원·확정 인원·예약 슬롯, 본인 초안·확정 구성·확정일·실제 시작일.
`GET /me/experiment/conditions`: 공통 모델의 근거·위험 기준·비중·실험 설정·지원 시나리오 목록.
`PUT /me/experiment/draft`, `POST /me/experiment/preview`, `POST /me/experiment/complete`:

```json
{"core_id":"CORE_V0.3","theme_ids":["semiconductor","ai"],"reason":"선택 이유","current_step":"review"}
```

`GET /comparison/rankings?basis=return|excess|mdd|volatility|sharpe|te|ir`: `registered`, `capacity`, `reserved`, `total`(실제 순위 대상), `pending`, 기간, 순위. MDD는 0에 가까울수록 우선, Volatility·TE는 오름차순, 나머지는 내림차순. 반올림 전 값이 같으면 같은 순위(competition rank). 종합점수 없음.
`GET /comparison/analytics`: reports, metric별 rankings, theme_selectors, outperformers, comparable. 인증 필수. 이메일·인증정보·비공개 이유는 공개 비교 응답에서 제외한다.

Excess는 Personal Return − CORE Return의 소수 수익률 차이이며 화면에서 ×100하여 %p로 표시한다. Volatility·TE는 연율 소수, Sharpe·IR은 무차원이다. 위험지표가 없으면 `null`/`—`를 사용한다. 가상 Sharpe의 무위험수익률 0은 모형의 기대수익률 설정(3%)과 별개다.

최근 데이터 주간은 2026-09-07~2026-09-11이며 직전 평가일 2026-09-04를 출발점으로 한다. **현재 달력상의 이번 주 실적이 아니다.** 전체 기간과 별도 표시한다. 집계되지 않은 이번 주 브리핑이나 기여도 문장을 자동 생성하지 않는다.

## 금융팀 확인 필요 계약

추가 데이터를 제공할 때 최소한 다음 정보를 포함해야 한다.

```json
{
  "participant_id":"Pxxx", "configuration_id":"immutable-id",
  "data_source":"FORWARD_ENGINE", "period":"WEEK",
  "timezone":"Asia/Seoul", "week_start":"YYYY-MM-DD",
  "valuation_start":"YYYY-MM-DD", "end":"YYYY-MM-DD", "as_of":"ISO-8601",
  "forward_started_at":"ISO-8601", "observations":0,
  "metrics":{"sortino":null},
  "target_weights":[], "applied_weights":[],
  "contribution":null,
  "quality":{"status":"INSUFFICIENT_HISTORY","missing_fields":[]}
}
```

- Sortino의 최소수용수익률, downside deviation·연율화 방식, 최소 관측 수, 0 분모·결측 처리.
- TE·IR 및 Volatility의 최소 유효 수익률 개수, 불완전 주간 표시 정책. 현재 Backend `perf_metrics`의 MIN_HISTORY=30은 NAV 행 수 기준이므로 ‘30개 일별 수익률’과 혼동하지 않아야 한다.
- 실제 Forward 시작·구성 확정·모델 기준일의 분리, 공통 시작·종료일이 다른 참가자의 비교 기간 정책.
- 주간 기준 시간대·금요일 마감·휴장일·직전 평가일 처리. 데이터 기준 주간과 현재 주간의 구분.
- 실제 적용 비중, holdings/trades/prices의 같은 snapshot ID와 평가 기준일.
- 누적/주간 자산 기여도 단위, 비용·현금·미설명 잔차, 합계 대사. Theme 총수익 기여도와 CORE 초과성과 기여도의 별도 정의·별도 필드.
- 새 구성에 대응하는 실제 엔진 계산 결과 또는 검증된 추가 공개 시나리오. 임의 Theme 이름 교체나 다른 사용자의 개인 장부 재연결은 허용하지 않는다.

## 저장·배포 제한

로컬 파일을 유지하면 서버 프로세스 재시작 후에도 신규 계정과 설정은 유지된다. seed 재실행은 이를 덮어쓰지 않는다. SQLite 원본과 자유 설계 DB를 함께 백업해야 한다. 기존 v1 가격 참조 DB도 별도로 보존한다.

현재 `render.demo.yaml`은 `CAPSTONE_DATA_DIR=/tmp/capstone-demo`, 무료 임시 파일시스템이다. 인스턴스 교체·재배포로 DB가 소실되면 기존 공개 seed만 재생성되며 **새 가입·초대·세션·설정은 복구되지 않는다**. 코드의 seed idempotence는 영속 디스크를 대신하지 않는다. 유료 디스크나 Production DB 전환은 실행하지 않았다. 이 문제를 해결하기 전 원격 환경에서 영속 가입 시연이 완료됐다고 말하지 않는다.

Vercel/Render 설정은 브라우저 → Next의 same-origin `/api/v1` proxy → `FASTAPI_INTERNAL_URL`의 기존 경계를 유지한다. HTTPS 배포에서 `AUTH_COOKIE_SECURE=true`, 웹 빌드 시 `NEXT_PUBLIC_CAPSTONE_DEMO=1`이 필요하다. 실제 배포 주소·프로젝트 연결이 저장소에 제공되지 않아 원격 배포와 로그인 smoke는 검증 대상 밖이다. 이번 변경은 로컬 코드이며 push·Production 초기화·과금 변경을 하지 않았다.

## 검증 명령

```bash
.venv/bin/python -m pytest -q
cd web
npm test
npx tsc --noEmit
NEXT_PUBLIC_CAPSTONE_DEMO=1 NEXT_PUBLIC_APP_PROFILE=local npm run build
cd ..
.venv/bin/python web/e2e/run_enrollment.py
```

브라우저 검증 명령은 별도 임시 DB·초대 2자리·서버·Chrome 세션을 생성한다. 새 비밀번호는 메모리에서만 생성하며 trace/video는 끈다. 기존 발표용 서버·DB는 초기화하지 않는다. PostgreSQL 실서비스·Vercel/Render 영속성 검증은 별도로 수행해야 한다.

## 최종 검증 기록 — 2026-09-20

- Backend 전체 회귀: `137 passed, 3 skipped`. 선택적 PostgreSQL 환경 검증 3개는 실행 환경 미제공으로 건너뛰었다. 기존 라이브러리 deprecation 경고가 남아 있다.
- Frontend: `npm test` 45개 통과, `npx tsc --noEmit` 통과, `NEXT_DIST_DIR=.next-unified-build NEXT_PUBLIC_CAPSTONE_DEMO=1 NEXT_PUBLIC_APP_PROFILE=local npm run build` 통과. 별도 lint script는 없고 Next 빌드의 lint/type 단계를 통과했다.
- 신규 가입 E2E: 독립 임시 DB의 11+2 비교군에서 신규 2명 가입·CORE·서로 다른 Theme/이유·새로고침 복원·생성·13명 비교·상세·재로그인·기존 사용자 전환을 desktop/mobile로 통과했다. API 프로세스를 실제 재시작한 뒤 13명 보고서와 신규 2명의 확정 구성이 유지됨을 확인했다.
- 기존 계정 E2E: `npx playwright test --config playwright.demo.config.ts` 통과. 기존 대시보드, 정렬, 상세, 새로고침, 로그아웃·다른 계정 로그인, 모바일을 검증했다.
- 가입 API: 중복 이메일·잘못된 초대·정원 초과·CSRF·동시 가입·중복 확정·서버 초안·CORE/Theme 규칙·이유 분리·seed 재실행·자유 설계 격리 테스트를 통과했다. 없는 시나리오는 NAV 없이 대기 상태를 유지한다.
- 기존 검증 수치: 13개 원래 계정의 NAV·CORE·지표 대사 통과. 최대 수치 차이 약 `3.71e-14`(부동소수점 오차). 활성 비교군은 별도로 12+1을 유지한다.
- 자유 설계 위험값 누락: 설계 DB에 기존 가격 39,042행을 연결한 후 기존 Backend의 예상 위험 계산이 복구됨을 확인했다. 가격만 복사하고 원본·사용자·NAV를 변경하지 않는 회귀 테스트 2개를 추가했다.
- 빌드 중 기존 `.next-*` 캐시에 생긴 번호 붙은 복제 타입 파일로 중복 선언 오류가 발생했다. 해당 생성 캐시만 정리했고 타입 검사를 끄지 않고 최종 빌드를 통과했다.
- 실제 배포 smoke, Production PostgreSQL, Render 재배포 후 데이터 보존은 미검증이다. 저장소에 없는 배포 프로젝트/주소를 추정하지 않았다. 기존 의존성을 사용했으며 lockfile/패키지 업그레이드는 하지 않았다.

발표용 로컬 비교군은 `professor-20260920`, 준비 참가자 12명 + `demo@example.com` 예약 1자리다. 이 이메일로 계정을 대신 생성하거나 비밀번호를 지정하지 않았다. 발표자는 저장소 밖의 개인 초대 파일을 이용해 직접 가입한다. 테스트용 계정은 별도 임시 DB에만 생성했다.

## 주요 변경 파일과 작업 범위

| 영역 | 주요 파일 |
| --- | --- |
| 예약 가입·초안·확정 | `src/db/models/demo_cohort.py`, `src/local/demo_cohort.py`, `src/api/services/enrollment_service.py`, `src/api/routers/enrollment.py`, 기존 auth/dependencies |
| 기존 자유 설계 보존·위험 입력 복구 | `src/api/design_workspace.py`, `src/api/design_prices.py`, `scripts/start_demo.py`, 기존 frontier/me/onboarding 연결 |
| 첫 설정 UI·단일 인증 메뉴 | `web/components/portfolio/ExperimentSetup.tsx`, `CoreConfirmation.tsx`, 기존 setup ThemeSelection/ReviewStep, login/signup, AppShell/AppSidebar |
| 비교·분석 | `src/api/services/comparison_service.py`, `web/components/performance/ComparisonAnalytics.tsx`, `DemoRanking.tsx`, `ParticipantPerformance.tsx`, `web/lib/api/comparison.ts` |
| 검증 | `tests/api/test_experiment_enrollment.py`, `test_design_prices.py`, 기존 capstone 테스트, `web/e2e/run_enrollment.py`, `enrollment.spec.ts`, `capstone.spec.ts`, `scripts/verify_capstone.py` |
| 공유 문서 | 이 운영 안내, `TEAM_CHANGE_SUMMARY.md`, README, Render 제한 안내 |

AI가 현재 코드·데이터를 점검하고 위 기능과 테스트·문서를 작성했다. 결과는 실행한 자동 검사와 브라우저 확인에 근거한다. 착수 전에 존재하던 미커밋 변경은 유지하며 그 위에 통합했다. 금융 모델·공개 seed NAV를 재작성하지 않았고, Git commit/push·원격 배포는 하지 않았다.
