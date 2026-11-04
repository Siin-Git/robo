# 주도주·수출 자료 및 성과 비교 인수 (2026-10-04)

## 기준과 범위

사용자 추가 조건대로 별도 `.work/strategy-comparison` worktree, `feat/strategy-comparison` 브랜치에서 구현·검증·커밋·푸시·develop 대상 Draft PR까지만 진행한다. 병합/배포는 첫 번째 세션의 검토 대상이다. Render 재설정은 사용자 후속 지시대로 별도로 남긴다.

직전 [원장 성과 인수](LEDGER_PERFORMANCE_RANKING.md), [통합 기록](INTEGRATION_EXECUTION.md), [실제 로컬 운용](LOCAL_REAL_OPERATION.md)과 코드를 먼저 읽었다. 최초 기준은 검증된 `09e92ada9ff69ea14005c0573554b224a3fba318`이며 당시 develop `cb5c778693556857f2c6c3e88d7ebb5b62076e76`을 포함한다. 다른 세션이 개인 비공개 fork로 동기화했지만 이 세션의 origin은 Siin-Git/robo를 그대로 유지한다. 작업 중 PR #19/#20이 통합된 최신 develop `250f315aaa1cf75e77bdaa3729993e4be8874f65`를 확인했고, `09e92ad`가 포함된 것을 검증한 뒤 아직 푸시하지 않은 작업 커밋을 충돌 없이 그 위로 rebase했다. 공유 develop/main에는 쓰지 않았다.

원래 체크아웃·3073/8073·실제 로컬 DB·예약 실행·다른 세션 서버를 변경하거나 종료하지 않았다. Render/Vercel/운영 DB/공유 secret/배포 workflow 설정 변경도 없다. 테스트 전용 파일은 `/private/tmp`, PostgreSQL14 UTF8은 55498, API는 8091, 웹은 3091, 빌드는 `.next-capstone-strategy*`를 사용한다. 기존 의존성은 링크하여 읽기만 했고 설치/갱신하지 않았다.

## Brief와 결정 기록

대상은 투자 전략·성과를 검토하는 사용자와 팀이다. 제공된 모델을 실제 거래 자산으로 오인하거나 다른 기준의 기대값과 실제값을 빼는 문제를 해결한다. 주요 흐름은 로그인 → 기존 투자 선택 화면의 전략 자료 → 전략/변형 선택 → 규칙·구성·시점·과거 성과 확인 → 기존 자산 Frontier/확정/원장 → 판단별 실제 결과와 비교 조건 확인이다.

P0는 자료 검증/연구 조회, 엄격한 예상/실제 비교, 승인된 같은 기간 benchmark 연결 준비다. 완료 조건은 인증·소유권 보존, 변형 자동 선택 없음, 모델 가격/원장 유입 거절, 동일 정의에서만 수치 차이 산출, 기대값 불변, 기존 금융 계산/원장/랭킹 회귀 통과다. 모델 코드/입력이 없는 신규 전략 운용 활성화와 실제 배포는 완료 범위에 포함하지 않는다.

결정: 제공 파일은 연구 데이터로 별도 등록한다. 대안인 ETF 대체나 월별 가격 보간은 원본 정의·주기·집행 시점을 왜곡한다. 기존 ETF 레지스트리에 inactive/ticker=null로 기록하고 인증된 연구 조회만 연다. 팀의 모델 채택·갱신 입력·한국 주식 집행 검증 이후 재검토한다. 예상/실제는 단위 변환이나 과거 기대값 재구성 대신 정의 대조를 선택한다. 미합의 benchmark는 후보로만 제시한다.

## 원본과 데이터 검증

Downloads의 네 파일을 직접 읽었다. XLSX 시트·셀·수식 캐시, PPTX 7개 슬라이드와 노트를 OOXML로 읽었으며 문구/명령 예시는 참고 자료로만 취급했다. 수식·매크로·자료 속 작업 명령은 실행하지 않았다. 원본 수정/저장소 복사 없음. 캐시는 제공값이며 Excel 재계산이나 원 모델의 독립 재현이 아니다.

| 파일 | SHA-256 | 근거 |
|---|---|---|
| 주도주_측정모델_20261001.xlsx | `ba041183aab3f3fd3c55dd36b6418a312c2359c5bc1ed1fb45ee527d1d1572ef` | README/GUIDE/TOP10/PARAM/REGIME/COMP/RAW/RECON/BT/PX |
| leader_stock_backtest.xlsx | `a7545d13c9d57d37e93680d148744d2b6e988cc92c2a61dca4101aa1715d4a30` | 요약/연별/월별/구성/매도/체결/룰 비교 |
| 01_Export_Strategy_Model_Performance.xlsx | `c757b74b7a951f45da8575d3a6f58240f868c33323b27b5626a01383fe0cf17c` | 13개 탭, 일별 NAV/월별 구성/리밸런싱/체결/비용 시나리오 |
| 02_Export_Strategy_Manager_Brief.pptx | `a9af7c47440710b77c3f158be7fb784afd32cdf735f4a9baf8b3a62f684f93c0` | 과거 Model와 앞으로 Actual Active/PM 정책 |

정규화 산출물 `data/strategy_research/20261004.json`: 세 가지 월별 시계열 각177개, 두 가지 일별 모델 시계열 각1,754개, 최신 주도주 목표안 및 수출 월별 구성. 수익률 fraction, level은 무차원 모델 지수다. 원화 계좌 평가액이 아니다. 인증된 `GET /api/v1/strategies`, `GET /api/v1/strategies/{id}?variant=...`는 연구 조회만 제공하며 변형을 생략하면 성과를 자동 선택하지 않는다. `GET /api/v1/benchmarks/definitions`는 후보/승인 정의만 조회한다. 원본의 Excel1900 날짜계를 확인했고 1904 날짜계/분수 날짜는 거절한다. 날짜 순서/중복, 양수/유한값, level 대비 수익률, 비중+현금 합계, 수출 신호/적용 지연을 검증한다.

월별 수익률/지수 최대 오차 `8.90e-15` 미만, 수출 일별 `9.34e-16` 미만, 수출 비중+현금 오차 `1.89e-15` 미만. 재추출 JSON은 바이트 단위 일치했다. 보수 체결에는 별도 일별 수익률 열이 없어 그 열의 일치 검증을 했다고 주장하지 않는다.

```sh
.venv/bin/python scripts/import_strategy_research.py --downloads /Users/jeongminchan/Downloads --output /private/tmp/strategy-research-new.json
```

출력은 새 파일만 허용한다. 가격 DB/계좌/네트워크/스케줄러에 연결하지 않는다. 새 자료 버전은 별도 원본/코드 검토 후 등록한다.

## 주도주: 정의·변형·시점

최신 측정은 2026-10-01, 비교일9/23, universe829개다. 원자료 금액은 억원, 비중/수익률 fraction, PX는 현재 KRW 종가 스냅샷이며 완전한 과거 일별 가격이 아니다. 선정은 EPS4주 상향·25주 percentile≥70·F만점·복합≥50, COMP40/30/20/10축, TOP10/WICS 중분류3종목 제한. F복합≥70은 ×1.4, sleeve 내 개별20% 한도, 빈자리 현금. buffer rank≤15·COMP≥65·F≥3, 주간 매도 점검, -8% 절반/-20% 청산이다.

최신 PARAM은 적용 base/추천 rate, 모든 레짐에서 TOP10 50%+KODEX200 A069500 50%다. RECON 캐시 "일치"는 독립 재계산 결과가 아니다. 최신 목표안의 주식은 TFE A425420, DI A003160, SFA반도체 A036540, SK이노베이션 A096770, 심텍 A222800 각5.8333%; 글로벌텍스프리 A204620, 세보엠이씨 A011560, 현대해상 A001450, iM금융지주 A139130, 셀트리온 A068270 각4.1667%다. 전체 합계100%이며 과거 모든 변형의 공통 구성이라고 표시하지 않는다.

별도 백테스트 구간은 2012-01-30–2026-09-29, 매수0.215%, 매도0.215%+거래세, 현금0%, KOSPI 가격지수 배당 제외다. 개별 주식 배당/분할/수정주가 처리는 코드가 필요하다.

| 변형 | 원본 CAGR | 원본 MDD | 차이 |
|---|---:|---:|---|
| TOP10 단독 | 17.69% | -53.31% | 주식 sleeve 전체 |
| TOP10 50%+KOSPI 50% | 13.93% | -41.69% | KOSPI 가격지수, 최신 KODEX200과 다름 |
| 레짐형 | 13.10% | -29.89% | TOP10 bull70/base50/rate40/bear30%, bear 잔여 현금 |

월별 날짜 2012-01-31–2026-09-30은 **월말 라벨**이며 마지막9/30이 실제 평가/체결일이 아니다. 실제 백테스트 종료는9/29다. 화면은 기존 계산기의 양 끝 누적수익률/관측 MDD와 원본 전체 기간 CAGR/MDD를 별도로 표시한다. 월별 MDD는 일별 MDD와 다를 수 있다. 이 통계를 기대수익률 전망·ETF 종가·실제 원장으로 넣지 않는다.

측정 파일 BT는9/23 종료, 별도 백테스트는9/29 종료이며 통계가 다르다. GUIDE의 백테스트는 신호 다음 거래일 종가, 최신 운용 제안은 신호일 동시호가다. 룩어헤드/데이터 공개시각/체결 결과가 달라 임의 선택하지 않았다. 초기2012-01–2013-03 전액 현금, 반복 룰 튜닝, 상장폐지 마지막 종가, 재공시 미반영도 재현 검토 대상이다.

필요 입력: `leader_stock` 모델 패키지·실행 진입점, 파라미터/레짐 버전, point-in-time 입력 캐시/발표·수정 시각, KRX·키움·DART·wisereport 자료/권한, 거래 달력·가격·배당·상장폐지 처리, 생성 시각/신호 효력일/RECON 코드, 갱신 책임자. 단일 ETF 실행기에 한국 개별주식·슬리브·목표 구성 버전·원화 집행 경로를 별도 검증해야 한다.

## 수출: 과거 R3와 미래 Actual Active

과거 R3는 ACTIVE FUND RULEBOOK v1.1, Live157을 과거에 적용, SIMPLE 최근3개월 YoY>0, F1 top30/buffer45, 동일가중이다. 목표 종목5%/거래 전7%, 섹터20%/25%, 신규 편입 청산일수≤10일(ADV10%), DATA_MISSING=HOLD_FROZEN. F1·동점·한도·부분체결·청산 세부 코드는 제공되지 않았다.

m월 수출 → m+2월 첫 거래일. 첫2019-07 신호 →9/2 리밸런싱/9/4 체결창 종료, 최신2026-07 신호 →9/1/9/3이다. 최신 구성35개는 잔여/부분체결을 포함하므로 목표top30과 구분했다. 목표 비중/체결창 종료 비중·전체 종목은 화면/JSON에서 조회한다.

| 시나리오 | 구간 | 집행/비용 | 마지막 모델 NAV | 원본 CAGR / MDD |
|---|---|---|---:|---|
| Historical R3 | 2019-08-01–2026-09-23 | 고정30억원, ADV10%, 3일, 25bp+MI | 9.390035887825022 | 37.9573% / -41.9431% |
| Conservative | 동일 | 같은 목표, ADV5%, 5일, 50bp+sqrt MI | 7.446207603953185 | 33.4358% / -42.4670% |

배당 제외/현금0%, 일별252 연율 위험, 수익률 fraction. 최초 월은9/2 전 현금이다. 원본 KOSPI 첫level0.996438714여서 원문 전체 기간 수익률과 양 끝 기준 수익률은 기준점이 다를 수 있다. 과거 자료를 사용자 확정 이후 실적으로 기록하지 않는다.

PPT의 미래 Active는 SIMPLE 상위50%+새 모델 후보 전체 → PM BUY/HOLD/TRIM/EXIT, 후보 내 veto/대체/비중조절·override 기록, Model/Actual12개월 병행 경로다. 후보 밖은 ResearchShadow다. 미래 제안 ADV5%/목표10일·최대5일도 과거 ADV10%/3일과 다르다. **실제 Active 성과는 제공되지 않았다.**

필요 입력: RULEBOOK/R3/F1/체결/MI 코드, `CAPACITY_R3_ALL.csv`, TRASS HS·시군구·국가→기업 매핑/Live157 버전, RF 제외/2026-07 동결 국가 자료, 신규 수출/발표 시각/수정 이력, 가격/배당/ADV/달력, PM 승인·권한·override 정책/갱신 책임자. 이후 모델 목표 → 품질 검증 → PM 판단 → 확정 목표/실제 주문 → 원장을 분리 연결해야 한다. 현재 파일만으로 실시간 갱신 경로 완료라고 표시하지 않는다.

## 최초 예상과 실제: 비교 정의

기존 기대값/판단 JSON은 불변이며 새 확정부터 정의를 추가 기록한다. 과거 값/정의를 복원하거나 업데이트하지 않는다.

| 축 | 기존 기대값 | 실제 원장 |
|---|---|---|
| 기간/단위 | 연간 전망 fraction_per_year | 관측 양 끝 누적 fraction; 위험만 최소 관측 충족 시 연간 통계 |
| 통화/비용 | KRW 모델, 비용 제외 | KRW NAV, 실제 거래비용 포함 |
| 배당 | 공급자 조정종가/일반 종가 경로 | 같은 공급 경로; 개별 배당 처리 추가 확인 필요 |
| 수익률 정의 | BL 연간 전략 전망 | 외부 입출금 없는 NAV 변동 |
| 위험 | 5년 주간 Ledoit-Wolf, W-FRI×52 | 일간 표본 표준편차, D×252 |
| TE 기준 | 확정 당시 사용자 선택 기본 구성 | CORE 버전 원장 |
| 판단 | 저장 판단 ID | 해당 효력 구간의 판단 ID |

`compare_metric`은 시작/끝·단위·통화·비용·배당·수익률/위험 정의·주기·판단·비교 기준이 모두 저장/일치하고 값/품질이 유효할 때만 actual−expected를 산출한다. 축별 불일치/미기록/관측 부족·위험 공백/오래된 가격 이유와 대조표를 표시한다. 단기 연율화·연간 기대값 기간 비례 환산·과거 예상값 생성은 없다.

동일 정의로 사전에 저장된 **테스트 전용** 예상1%와 기존 계산기 NAV100→102는 차이+1%p다. UI +1.23%p도 검사했다. 현재 실제 저장된 기대값은 위 기준이 달라 수치 차이가 null인 것이 맞다. 실제 사용자를 위한 동일 기간 예상 모델 생산까지 구현한 것은 아니다. 앞으로 비용 포함 예상 모델을 저장할지/비용 제외 실제 경로를 재구성할지 결정과 검증이 필요하다.

조회 종료를 다음 판단 효력일/현재 KST 날짜 중 앞선 경계로 제한한다. 미래 NAV가 존재하는 검사에서도 3/6개월은 NOT_REACHED와 null이다. 실제 장기 기록을 만들지 않는다.

## 시장·안전자산

프로젝트/저장소에서 합의된 시장·안전자산 정의를 찾지 못했다. 전략 자료의 과거 KOSPI를 서비스 전체 합의로 승격하지 않았다. 기존 CORE 원장 및 사용자 선택 기본 구성의 비용 제외 매수 후 보유 가격 비교를 보존했다.

현재 `config/performance_benchmarks.yaml`의 `definitions: {}`. 승인자/일시/버전/정의를 기록해야 연결한다. KRW0% 현금 또는 검토된 `data/reference_benchmarks/*.csv`를 기존 `evaluate_levels`로 계산할 수 있다. 실제 start/end 날짜가 모두 정확히 있어야 하며 보간·환율 추정 없음. gross 지수와 net 계좌를 나란히 표시하더라도 비용/배당 기준이 다르면 차이는 보류한다.

| 후보 | 통화·배당·비용 | 필요한 결정/입력 |
|---|---|---|
| KOSPI 가격지수 | KRW, 배당 제외, 지수 gross | 실제 같은 날짜 일별 출처/권한; 전략 자료와 가까움 |
| KOSPI 총수익지수 | KRW, 배당 재투자, 지수 gross | 배당 포함 정책/해당 일별 지수 |
| 원화 무이자 현금 | KRW, 배당/비용 없음, 0% | 원장 현금 관행과 같지만 모델 기대 현금3%와 다름; 팀 채택 |
| KOFR 누적 | KRW, 배당 없음, 금리 기준 gross | 복리·일수·휴일·공시 지연 규칙/같은 기간 금리 |

후보 출처: [KRX 총수익지수 설명](https://eindex.krx.co.kr/contents/GLB/05/0502/0502050600/GLB0502050600.jsp), [한국은행 KOFR 설명](https://www.bok.or.kr/portal/main/contents.do?menuNo=201069). 출처는 팀 채택/승인이 아니다. 임의 ETF를 쓰지 않았다.

## 필요한 팀 결정

비동기 질문을 전달했고 답변은 아직 없다. Render 메시지를 모델 결정의 답으로 해석하지 않았다.

1. 주도주 변형/체결: 연구 조회 유지 / TOP10+다음 거래일 종가 / 50:50+다음 거래일 종가 / 레짐형. 동시호가를 원하면 공개시각·룩어헤드 검증이 필요하다. KOSPI와 KODEX200의 배당/비용/가격 정의도 구분해야 한다. 선택에 따라 위험/성과/집행이 바뀐다.
2. 수출: 과거 Model와 미래 PM Active의 대상, ADV/부분체결 비용, override 정책/갱신 책임자. 둘을 섞으면 인간 판단 기여도와 비용 영향이 왜곡된다.
3. 예상/실제: 엄격한 비교 보류 유지 / 비용 제외 실제 재구성 / 앞으로 비용 포함 예상 모델 저장. 기간·정의·주기·TE 기준까지 일치해야 한다. 과거 기대값은 수정하지 않는다.
4. 시장/안전자산: 후보 유지 / KOSPI price+KRW0% / KOSPI TR+KOFR 등 명시적 채택. 같은 기간 자료·비용·배당/복리를 함께 결정해야 한다.

답변 없이 자료 검증/조회/표시·비교 엔진·승인 정의 연결 준비를 진행했다. 모델 정의/입력 해결 전 active/frontier/confirmation/price-store는 열지 않는다.

## 변경 파일·커밋·충돌

- 전략 `9f1cac6`: `config/themes_v01.yaml`, `strategy_research.yaml`, `data/strategy_research/20261004.json`, `src/strategies/*`, `scripts/import_strategy_research.py`, API main/strategies/strategy_service/onboarding_service/view_service, 프론트 전략 페이지/StrategyCatalog/ThemeSelection/lib/api/strategies 및 검사.
- 예상/실제 `4965a05`: `src/forward/expectation_comparison.py`, API decision_service, API/forward 검사, review/ExpectationComparison/lib/api/decisions/UI 검사.
- 기준 `b8398dd`: `config/performance_benchmarks.yaml`, API benchmark_definition_service/reference_service/benchmarks, dashboard/performance-data/BenchmarkOptions 및 검사.
- 시연 연결 보완 `6a69e08`: 초기 설정 중 연구 조회 허용·모바일 대조표·기준 수치 차이 검사·PC/모바일 신규 확정 및 연구 조회 E2E.
- 인수 문서: 본 문서, `INTEGRATION_EXECUTION.md`, `web/e2e/strategy-comparison.spec.ts`, `web/playwright.strategy.config.ts`, `web/components/layout/AppShell.tsx`의 초기 설정 중 연구 조회 허용.

스키마/마이그레이션/집행 엔진/예약/운영 정책 변경 없음. 충돌 가능성이 높은 파일은 decision_service/onboarding_service/reference_service/main, dashboard/review/ThemeSelection/AppShell, themes_v01, INTEGRATION_EXECUTION이다. 현재 최신 develop 추가 변경은 운영 workflow/문서/inventory/Render blueprint/기존 E2E timeout이며 직접 충돌은 없었다. 새 비교 메타데이터는 새 판단에만 추가해야 하며, `09e92ad`의 내부 NAV 보존/null 그래프/위험 순위 자격을 유지해야 한다.

## 검증

최종 develop 기준 재검사 완료. PR/CI 결과는 Draft PR 본문과 최종 인수 응답에 기록한다. 운영 검증은 수행하지 않았다.

- 최신 develop 기준 Python3.11.15+폐기 PostgreSQL14 UTF8/55498 전체 **579 passed, 0 failed, 0 skipped**. 인증/운용 분리·불변 판단·동시성·마이그레이션·실제 dump/restore와 Excel epoch 거절 포함. 관련 최종 **37 passed**. 그 뒤 승인된 net 기준의 수치 차이 검사 1개를 추가하여 benchmark 관련 **6 passed**도 확인했다.
- 첫 전체 실행의 PG3건 실패는 sandbox loopback 접속 제한이다. 전용 클러스터 접근 권한/모든 테스트 URL을 설정하고 재실행했다. 제품 코드/테스트를 우회하지 않았다.
- Vitest **71 passed/16 files**, 최종 production build/타입 검사 통과. 별도 lint 스크립트 없음. 의존성/락파일 변경 없음.
- Chrome1440/390: 신규 전략/비교 및 신규 계정의 기존 ETF Frontier/확정/새 판단/성과 대기 **4 passed**, 기존 0/1/복수 평가·현재/대기/이전 판단·공통 기간/기여도·랭킹 자동 갱신 **2 passed**. 읽기 후 판단/성과 불변·넘침/페이지 오류 없음 확인. 첫 신규 검사의 개인 시작일 assertion을 fixture의10/1로 바로잡았다. 신규 미확정 계정의 AppShell 안내가 전략 조회를 설정 화면으로 되돌리던 문제도 찾아 조회 페이지를 허용한 뒤 전체 흐름을 재검증했다. API 인증/편입 거절은 유지했다. 모바일 대조표는 읽기 쉬운 너비와 좌우 스크롤을 적용하고 화면을 확인했다.
- 재추출 cmp 일치, 시점/단위/가격·수익률/비중 검증. 실제 모델 재현/실시간 갱신/한국 개별주식 집행은 미검증.
- 생성된 DB 보고서/covariance/Next 타입 설정은 별도 보존하고 원복한다. 커밋 제외. 원본·로그인 정보·secret도 제외한다.

로그는 `/private/tmp/robo-strategy-backend-full-final.log`, `robo-strategy-backend-latest-develop.log`, `robo-strategy-targeted-final.log`, `robo-strategy-benchmark-final.log`, `robo-strategy-frontend-final.log`, `robo-strategy-build-handoff.log`, `robo-strategy-e2e-handoff.log`, `robo-strategy-e2e-complete-final.log`, `robo-strategy-e2e-ledger-final.log`다. 스크린샷/비공개 로그인 정보는 `/private/tmp/robo-strategy-browser-20261004`에만 있다.

## 월요일 시연·수요일 남은 일

월요일10/5: 격리 [3091 로그인](http://127.0.0.1:3091/login) → 신규 계정(예: 참여자09)의 기존 자산 Frontier/확정/판단 → 전략 자료에서 주도주 변형/월말 라벨과 수출 m+2 시점/구성 → dashboard/review의 CORE/선택 기준/비교 사유. fixture 시계는10/5 KST, **TEST_FIXTURE**이며 실제 월요일 운용 성과가 아니다. 신규 전략 운용 완료나 실제3/6개월 성과로 발표하지 않는다.

새 환경 재현은 새 `/private/tmp` 디렉터리/미사용 포트로 한다:

```sh
.venv/bin/python scripts/start_ledger_comparison_demo.py --directory /private/tmp/robo-strategy-new-demo --port 3091 --api-port 8091
# web 디렉터리, 전용 서버가 실행 중일 때
E2E_OPERATIONS_DATA_DIR=/private/tmp/robo-strategy-new-demo E2E_BASE_URL=http://127.0.0.1:3091 npx playwright test --config playwright.strategy.config.ts
```

수요일10/7까지 모델 담당자 코드/입력/발표 시각 제공, 팀의 변형/체결/비용/배당/benchmark 결정, 선택한 정의의 point-in-time 재현, 한국 주식/부분체결 경로 설계·검증, 앞으로 저장할 동일 기준 예상 모델 정책이 필요하다. 자료가 없으면 연구 조회 상태를 유지한다. 실제 운용/장기 성과는 실제 기록 누적 후 별도 검증한다. 첫 세션은 Draft PR 통합 검토/병합/운영 범위/Render 재설정을 담당한다.

| 요구 | 구현 완료 | 운영 검증 완료 | 자료·팀 결정 필요 |
|---|---|---|---|
| 주도주·수출 | 원본 분석/검증·연구 등록/조회·변형 선택·기존 계산기·활성화 거절 | 없음 | 변형/시점/코드/입력/집행; 운용 연결 미완료 |
| 최초 예상·실제 | 정의 대조·조건부 수치 차이·사유·미래/효력 구간 제한 | 없음 | 실제 저장 기대값의 동일 기준 모델; 현재 차이 보류 |
| 시장·안전자산 | CORE/선택 기준 보존·후보·승인 정의 경로·정확한 기간 검사 | 없음 | 채택/일별 자료/배당·비용·복리; 현재 비활성 |
| 검증·반영 | 격리 검증·기능 커밋·브랜치 푸시·Draft PR | 배포 없음 | 첫 세션의 통합 검토/병합/배포 |

AI는 자료 읽기/코드·검사·문서 작성/명령 검증을 수행했다. 모델 채택/운영 승인은 사람의 결정으로 남긴다. 실행 증거가 있는 기능만 완료로 기록한다.

현재 검증 화면 재실행(기존 fixture 전용):

```sh
.venv/bin/python scripts/start_monday_demo.py --directory /private/tmp/robo-strategy-browser-20261004 --serve-api --api-port 8091
# web 디렉터리, 최종 production 빌드가 이미 있을 때
FASTAPI_INTERNAL_URL=http://127.0.0.1:8091 NEXT_DIST_DIR=.next-capstone-strategy-final2 npm run start -- --hostname 127.0.0.1 --port 3091
```

현재 서버에는 고정 fixture 시계가 적용된다. 최초 설계 확인은 아직 미확정인 참여자09 이후로 시연하고, 연구/비교 조회는 참여자01로 시연한다. 신규 확정 E2E는 새 fixture의 참여자07/08을 사용하므로 같은 자료에서 반복 실행하지 않는다. 시연/비밀번호를 운영 환경에 복사하지 않는다.
