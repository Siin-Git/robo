# 원장 성과·그래프·참여자 비교 인수 기록 (2026-10-04)

## 범위와 상태

기준 develop은 PR #18 병합 커밋 `cb5c778`이다. 별도 worktree `.work/ledger-performance-ranking`, 브랜치 `feat/ledger-performance-ranking`에서 구현했다. 원본 루트/robo 체크아웃과 실제 앱 worktree의 미커밋 변경을 보존한다. 푸시·병합·배포, 운영 DB 접근, DB 스키마/모델/배치/스케줄러 변경은 하지 않는다.

**기존 3073 실제 앱은 이번 변경을 반영하지 않은 채 유지했다.** 새 코드는 별도 3085 테스트 화면에서 검증한다. 실제 DB로 시연 fixture를 복사하지 않는다. 3073 전환은 후속 로컬 반영 작업이며 기존 DB·설정·예약 실행을 그대로 사용해야 한다.

## 화면별 출처

| 화면 | 변경 전 (현재 로컬 프로필) | 변경 후 |
| --- | --- | --- |
| `/dashboard` 내 운용 성과·누적수익률·기여도 | `/me/performance/dashboard`, 운용 DB의 NAV/보유/체결 | 같은 계산과 원장 유지. 원화 평가액/100 기준점, 관측일, 공통 기간 조회 보완 |
| `/performance` | market comparison 모드에서는 `/me/comparison`의 현재 목표 비중 × 과거 가격. 다른 모드의 기존 그래프는 별도 NAV/지표/기준 API 사용 | 기본은 대시보드와 같은 원장 성과 컴포넌트/API. 이전 화면은 `?source=demo`에서 보존 |
| `/ranking`, 참여자 비교 그래프/상세 | `/comparison/rankings`, `/comparison/analytics`, `/participants/{id}/comparison`: 인증 DB의 시연 NAV 또는 현재 비중에 과거 시장 가격을 적용한 비교 | `/me/performance/comparison`: 인증 DB의 활성 코호트/참여자 신원 + 운용 DB의 확정 이후 실제 NAV. 표시 이름·정규화 성과만 공유 |
| 자산별 기여도 | dashboard와 `/me/performance/contributions`: 실제 보유 평가액과 체결, 비용 | 기존 `calculate_report`의 손익 연결 방식 유지. `comparison=common`도 동일한 입력 구간 사용 |

기존 가격 비교는 `/dashboard?source=demo`, `/ranking?source=demo`, `/performance?source=demo`, `/participants/{id}?source=demo`에서 명시적으로 구분한다. 시연 화면의 상세 링크도 이 출처를 유지한다. 사용자 선택 기본 구성의 매수 후 보유 가격 비교는 기존 정의와 구분 문구를 유지한다. 시장·안전자산 정의나 최초 예상↔실제 수치 비교를 추가하지 않았다.

## 공통 구간과 단위

- 개인 성과 기본 조회는 현재 KST 효력 판단 이후의 유효 관측 기간이다. 미래 대기 판단으로 현재 성과 시작일을 바꾸지 않는다. 과거 판단 상세 API와 기록도 유지한다.
- 비교 후보는 현재 코호트의 활성 사용자/참여자다. 준비 참가자와 등록 슬롯 모두 포함하며, 운용 DB의 disabled 신원 참조를 로그인 사용자 상태로 오해하지 않는다.
- 효력이 발생한 판단과 유효 평가 2건 이상을 가진 후보들의 **실제 관측 날짜 교집합**을 사용한다. 요청 기간은 기존 `PERIODS`/계산기에서 제한한다. 최초 확정 효력일 전/현재 날짜 이후의 기록을 포함하지 않는다.
- 공통 평가일 2건 미만, 비교 인원/해당 지표 산출 인원 2명 미만이면 순위를 만들지 않고 사유를 반환한다. 결측 날짜를 채우거나 선을 연결하지 않는다.
- 비교 화면의 `공통 기간의 내 성과·기여도`는 `/dashboard?comparison=common&period=...`로 이동한다. 같은 start/end/dates로 계산한 dashboard와 contributions의 수익률은 랭킹 행과 정확히 동일하다. 개인 전체 구간과 공통 구간은 서로 다를 수 있으며 화면에서 기간을 구분한다.
- CORE는 기존 `CORE_V0.3` 계좌 원장이다. 비교 그래프의 CORE 선은 선택 참여자에 연결된 CORE 원장이며, 같은 관측 시작/종료일이 없으면 수익률·차이를 제공하지 않는다. 위험 순위가 불가능해도 계산 가능한 누적수익률/지수 그래프는 유지한다.
- 원화 NAV는 `valuation.nav_krw` / 현금은 `cash_krw`, 비교 그래프는 `index100`, 수익률·기여도는 fraction이다. UI는 단위 변환/형식 표시만 한다.
- 0건은 대기, 1건은 평가액과 최초 기준점 100만 제공한다. 수익률/기여도/변동성/순위는 임의로 0으로 채우지 않는다. 2건부터 기존 계산 가능 지표를 제공한다. 연율 위험 지표는 기존 유효 수익률 30개 및 가격 품질 조건을 유지한다.
- 마지막 유효 평가일과 불완전한 마지막 원장 평가일을 구분한다. 비교 API는 타인의 원화 잔액·보유·주문·계좌 ID·판단 ID·이메일을 제공하지 않는다. 기존 소유권 검사도 유지한다.
- 대시보드와 비교 조회는 15초 자동 갱신한다. 새로운 금융 임계값, 무위험수익률, 자동 거래 규칙은 추가하지 않았다.

## API/주요 파일

- 기존 `/me/performance/dashboard`, `/me/performance/contributions`: `comparison=individual` 기본, `common` 선택. `period`는 기존 ALL/1M/3M/6M/1Y.
- 추가 `/me/performance/comparison?period=ALL&basis=return`: return/excess/mdd/volatility. 공개 비교에 필요한 정규화 성과만 반환.
- `src/api/services/ledger_comparison_service.py`: 코호트/공통 관측 구간/표시 계약. 기존 `performance_report_service.dashboard` → `src/forward/performance_report.calculate_report` 재사용.
- `web/components/performance/LedgerComparison.tsx`: 실제 비교 화면. 기존 차트 재사용, 결측 연결 비활성화, 모바일 표 가로 스크롤.
- 스키마 마이그레이션 없음. 배치 원장 쓰기나 주기 정책 변경 없음.

## 검증

- 전체 백엔드 (Python 3.11.15, SQLite + 폐기용 PostgreSQL 14.19 UTF8 / 55495): **539 passed, 0 skipped** (최종 로그 `/private/tmp/robo-ledger-backend-verified.log`).
- 관련 원장 비교/현재·대기 판단/성과 계산 회귀: **27 passed**.
- 프론트 Vitest: **65 passed / 14 files**. Next.js production build 및 타입 검사 통과.
- Chrome 브라우저: **2 passed**, 1440px/390px. 로그인, 0/1/복수 관측, performance 동일성, 공통 기간 성과·기여도·랭킹 일치, 현재/대기 및 이전 판단 상세, 새 평가 추가 후 15초 자동 랭킹 갱신, 시연 화면/참여자 상세 보존, 가로 넘침 없음 확인. 모바일 스크린샷 확인 후 표의 잘못된 줄바꿈을 가로 스크롤로 보완했다.
- API 회귀: 서로 다른 시작일, 공통 날짜 없음/한 날짜, 기록 추가, 효력일 전/후, 원화 NAV/기여도 합계, CORE 누락, 짧은 위험 기록, 비공개 원장/판단 접근 거절, 인증/운용 DB 분리와 코호트 경계.
- 처음 PostgreSQL 검사에서 폐기용 DB를 SQL_ASCII로 만든 환경 오류로 4건 실패했다. UTF8 폐기용 DB로 수정했고 테스트를 삭제·건너뛰거나 제품 코드를 우회하지 않았다.
- 실제 운용 데이터: 읽기 전용 확인 당시 운용 판단 3개, 대기 주문 8개, 가격 42,010개, 체결/보유/평가 0개. 실제 성과·기여도·순위/위험 지표는 아직 산출할 수 없다. 합성 주문·평가를 넣지 않았다. 실제 예약 실행의 기존 작업 이력은 유지한다.
- Render/Vercel·원격 운용 DB/운영 배포 미검증. 본 작업에서 접근하지 않음.

로컬 기능 커밋: 백엔드 `0411ff3`, 화면 `675cd3d`. 생성된 DB 검증 보고서·covariance·중복 Next 타입은 이번 테스트 산출물로 따로 보존하고 원래 파일로 복원했으며 기능 커밋에 포함하지 않았다. 중복 Next 생성 타입에 의한 빌드 오류도 제품 코드/검사를 우회하지 않고 격리된 production 빌드로 재검증했다.

## 별도 로컬 확인

실행 중: <http://127.0.0.1:3085/login>, API 8085. 최종 코드의 production 빌드(`.next-capstone-build`)를 실행한다. 데이터는 `/private/tmp/robo-ledger-comparison-final-20261004`의 **TEST_FIXTURE / 고정 시계 2026-10-05 KST**다. 실제 운용 실적으로 사용하지 않는다. 비밀번호는 해당 디렉터리의 비공개 `accounts.json`/`accounts.md`에서만 확인한다.

- 참여자 01: 현재 v1 + 적용 대기 v2, 평가 3건.
- 참여자 02: 현재 새 판단의 평가 0건, 이전 v1의 평가 2건은 상세 조회 가능.
- 참여자 03: 현재 판단 평가 1건, 원화 평가액 + 기준점만 표시.
- 참여자 04: 다른 시작일, 평가 2건. 01과 공통 구간 비교.
- 참여자 05: 미확정 신규 사용자.
- 참여자 06: 새 평가 추가/자동 갱신 검증용. 브라우저 검증 후 평가 2건.

순서: 01 로그인 → dashboard/performance → ranking → `공통 기간의 내 성과·기여도` → review → 로그아웃/다른 계정 로그인. 과거 가격 비교는 `?source=demo` 링크로 구분한다.

새 폐기용 시연 환경 재현 (빈 /private/tmp 디렉터리와 사용하지 않는 포트 필요):

```sh
.venv/bin/python scripts/start_ledger_comparison_demo.py --directory /private/tmp/robo-ledger-new --port 3085 --api-port 8085
```

기존 fixture API 재실행은 `start_monday_demo.py --directory <fixture> --serve-api --api-port 8085`, 현재 production 프론트 재실행은 `FASTAPI_INTERNAL_URL=http://127.0.0.1:8085 NEXT_DIST_DIR=.next-capstone-build npm run start -- --hostname 127.0.0.1 --port 3085` (web 디렉터리). 실행 터미널 Ctrl+C로 해당 테스트 서버만 종료한다. 3073 실제 앱의 시작/중지 바로가기와 스케줄러는 그대로 사용한다.

```sh
# 위 격리 서버가 실행된 상태에서 web 디렉터리
E2E_OPERATIONS_DATA_DIR=/private/tmp/robo-ledger-comparison-final-20261004 E2E_BASE_URL=http://127.0.0.1:3085 npx playwright test --config playwright.ledger.config.ts
```

남은 일은 검토 후 코드 통합/3073 로컬 반영, 실제 효력일·체결·평가 누적 후 수치 확인이다. 실제 예약 실행·금융 정책을 변경하거나 실적을 선생성하는 방식으로 해결하지 않는다.
