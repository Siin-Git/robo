# 교수님 시연용 MVP

## 실행

저장소의 `robo/` 폴더에서 실행합니다. 기존 `.venv`, `web/node_modules`가 있으면 설치를 반복할 필요가 없습니다.

```sh
.venv/bin/python scripts/start_demo.py
```

Windows에서는 `.venv\Scripts\python.exe scripts\start_demo.py`를 사용합니다.
데모 웹: http://127.0.0.1:3001/login · API: http://127.0.0.1:8001
터미널의 Ctrl+C로 데모 서버 두 개를 종료합니다. 기존 3000/8000 서버는 건드리지 않습니다.

새 환경에서는 Python 가상환경에 `pip install -r requirements.txt`, `web/`에서 `npm ci`를 먼저 실행합니다.

## 계정과 seed

- ID: `capstone01@example.com` ~ `capstone13@example.com`
- 공통 비밀번호: `Capstone-Demo-2026!`
- 표시 이름: 참여자 01 ~ 참여자 13. 실제 팀원 이름은 제공되지 않아 번호로 표시합니다.
- 공개된 로컬 데모 전용 계정입니다. 실서비스 계정이나 비밀번호가 아닙니다.

```sh
.venv/bin/python -m src.local.seed_capstone
```

실행 스크립트가 seed도 자동 호출합니다. 반복 실행은 기존 데모 계정·NAV·비밀번호를 덮어쓰지 않습니다.
`data/capstone_demo.db`만 사용하며 기존 `forward_local.db`는 유지합니다.

## 3분 시연 순서

1. 01 계정 로그인: 반도체 + AI, Portfolio NAV와 Return/CORE/Excess 확인.
2. NAV 두 선이 100에서 출발하는 것을 설명. 가상 데이터임을 명시.
3. “13명 성과 비교” 클릭. 기본 Return 1위 참여자 01 확인.
4. Sharpe로 정렬: 1위 참여자 03. MDD/Volatility로 정렬: 1위 참여자 13.
5. 참여자 02 행 클릭: 방산 + 원자력, CORE 미달 성과, 구성과 자산 비중 비교 확인.
6. 로그아웃 → 03 계정 로그인 → 전력망 + 사이버보안 및 다른 성과 확인.
7. 새로고침해 같은 데이터가 유지되는지 확인.

## 데이터·구현 결정

- 기존 Next.js/FastAPI/SQLite 인증을 재사용하며 스키마 변경은 없습니다.
- `CAPSTONE_DEMO=1` + `APP_PROFILE=local`일 때만 별도 DB와 비교 API를 활성화합니다.
- `NEXT_PUBLIC_CAPSTONE_DEMO=1`로 대시보드와 랭킹의 데모 화면을 선택합니다. 일반 모드의 기존 화면은 유지합니다.
- CORE는 기존 frozen CORE V0.3 비중입니다. 테마 비중은 기존 `theme_target_weights`와 `fund_from_equities`를 사용합니다.
- 개인 NAV는 테마별로 고정된 합성 시나리오를 조합한 **화면 검증용 fixture**입니다. 실제 ETF 가격·거래·보유 장부에서 재현한 수익률이 아닙니다. 전략·리밸런싱·새 금융 엔진을 만들지 않았습니다.
- 최종 검증에서 중간 NAV에 최대 0.25% 이내의 고정된 작은 불규칙성을 추가했습니다. 시작·최종 NAV는 유지하며 모든 지표는 해당 NAV에서 재계산합니다. 차트는 일별 점을 직선으로 연결합니다.
- 2026-04-01 ~ 2026-09-11의 같은 118개 평일 인덱스이며 실제 거래소 휴장일 달력을 주장하지 않습니다. CORE 경로는 13명 모두 동일하고 시작 NAV는 100입니다.
- NAV는 지수 단위입니다. 거래 실행용 장부로 사용하지 않습니다.
- `comparison_service.detail()`이 DB NAV에서 기존 `perf_metrics()`를 호출합니다. 대시보드·랭킹·상세의 유일한 지표 응답입니다.
- Excess = 개인 누적수익률 − CORE 누적수익률, 표시 단위 %p.
- Volatility/Sharpe는 일별 가상 NAV의 실현값입니다. 표본 표준편차, 연율화 252일, 무위험수익률 0이라는 기존 계산을 유지합니다.
- Return/Excess/Sharpe는 높은 순, MDD는 0에 가까운 순, Volatility는 낮은 순입니다. 동률은 참여자 ID 순으로 안정 정렬합니다.
- 비교 API는 인증된 사용자에게 데모 참여자의 이름·테마·지표·NAV·비중만 제공합니다. 기존 소유자 전용 API는 그대로 보호합니다.
- 데모에서는 가입과 포트폴리오/View 변경을 차단합니다. Frontier·기여도 화면은 데모 경로에서 제외합니다.
- 13개 선 전체 차트는 가독성을 위해 생략했습니다.

## 주요 파일

- `src/local/capstone.py`, `src/local/seed_capstone.py`: 13명, 계정, 합성 NAV fixture
- `src/api/services/comparison_service.py`: 단일 성과 계약과 정렬
- `src/api/routers/{me,participants,performance}.py`: 인증된 읽기 전용 API
- `web/components/dashboard/ParticipantPerformance.tsx`: 대시보드·참여자 상세 공통 UI
- `web/components/performance/DemoRanking.tsx`: 정렬·상위 3명·행 이동
- `web/app/(app)/participants/[participantId]/page.tsx`: 상세 경로
- `scripts/start_demo.py`: 격리된 실행·seed

## 검증 명령

```sh
.venv/bin/python -m pytest -q
cd web
npm test
npx tsc --noEmit
NEXT_PUBLIC_CAPSTONE_DEMO=1 NEXT_PUBLIC_APP_PROFILE=local NEXT_DIST_DIR=.next-capstone-build npm run build
# start_demo.py 실행 후, 설치된 Google Chrome 사용
npx playwright test --config playwright.demo.config.ts --reporter=line
```

E2E는 계정 01/03 전환, 새로고침, 13명·5개 정렬, 실제 행 클릭, 상세/대시보드 수치 일치, NAV 두 선, 모바일 가로 넘침과 콘솔 오류를 확인합니다.
스크린샷은 `web/test-results/capstone-*.png`에 저장됩니다.

13명 전원에 대한 독립 공식 검산과 실제 브라우저 감사 결과는 [최종 검증](FINAL_VERIFICATION.md)에 있습니다.
재실행은 먼저 `python scripts/verify_capstone.py`, 이후 `web/`에서 `npx playwright test --config playwright.audit.config.ts --reporter=line` 순서입니다.

## 한계와 제외 범위

- 로컬 단일 서버에서 시연합니다. 외부 배포·13명의 외부 기기 접속 설정은 포함하지 않습니다.
- 실제 Forward Test 실적이 아닙니다. 과거 ETF 가격 기반 백테스트도 아닙니다.
- 테마는 사전 배정된 고정값입니다. 실제 이름·계정 개인화와 테마 변경은 후속 작업입니다.
- 새로운 엔진, 거래비용, 리밸런싱, Attribution/Contribution, 추가 위험 지표, PostgreSQL은 구현하지 않았습니다.
- 기존 운영 `/ready`는 시장 가격 저장소를 전제합니다. 데모 실행은 `/health`와 데모 비교 API를 사용해 검증합니다.
