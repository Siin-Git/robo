# 원장 성과 비교 화면 정리 — 2026-10-05

> 2026-10-05 통합 상태: 이 기능은 기존 Draft PR #1에 함께 반영한다. 아래는 해당 기능의 최초 작업 기록이며, 현재 통합 검증과 배포 범위는 [CAPSTONE_UNIFIED_HANDOFF.md](CAPSTONE_UNIFIED_HANDOFF.md)를 기준으로 확인한다.

## 목적과 완료 기준

기본 `/ranking`의 긴 표·검증 설명을 기존 `/ranking?source=demo`의 카드 구성으로 정리한다. 교수 시연에서 성과 요약 → 비교 그래프 → 참여자 순위 → 편입 테마별 성과 순서로 설명할 수 있어야 한다. 기본 화면의 원장 수치·관측 날짜·CORE 비교는 그대로 유지한다.

완료 기준은 다음과 같다.

- 원장 API만 사용하며 기존 15명의 수익률·위험 지표·순위·관측 값이 동일하다.
- 전체 / 나와 기준 / 상위 5명, 참여자 선택, 네 가지 순위 기준이 동작한다.
- 긴 비교 조건과 선택 참여자의 품질 상태는 기본으로 접힌 ‘비교 기준 보기’에 보관한다.
- 관측 부족·평가 공백·오래된 가격의 보류 상태를 보존하고, 데스크톱·모바일에서 확인한다.

운영 배포, 가격 수집, 참가자 확정, 공동 T0, 주문·체결·평가 생성은 이번 범위에 포함하지 않는다. 3073·3099·3103과 운영 서비스·예약 실행은 변경하지 않았다.

## 구현과 판단

`LedgerComparison`에 기존 디자인의 CSS 모듈·공통 테이블·차트를 재사용했다. `ThemeComparison`은 화면 렌더링 입력을 좁혀 기존 시연과 원장 화면이 공유한다. 이 컴포넌트를 사용하는 것만으로 과거 가격 API를 호출하지 않는다. 차트는 서버의 날짜별 기준 100 지수와 null을 그대로 표시하며, 내부 관측을 버리거나 결측 구간을 연결하지 않는다.

기존 원장 비교 API에 읽기 전용 필드만 추가했다. DB 마이그레이션은 없다.

- `return_rank`, `return_ranked`: 기존의 정밀 값·동점 규칙으로 서버가 계산한다. 표를 MDD·변동성 순으로 바꾸어도 상단 수익률 순위와 ‘상위 5명’은 유지된다.
- `themes`: 선택 초안이나 현재 View 대신 같은 보고 기간의 보유 기록에서 편입 테마 ID만 추출한다. 다른 참가자의 수량·금액·주문·판단을 공개하지 않는다.
- `theme_selectors`: 같은 기간 참여자들의 포트폴리오 수익률·CORE 차이·관측 MDD 평균과 각 지표의 관측 인원을 서버에서 반환한다. 두 테마 편입자는 양쪽에 포함한다. 이는 테마 자체의 수익률이 아니다.

위험 분포는 서버의 변동성 품질 조건을 통과한 참여자가 두 명 이상일 때만 표시한다. 11개 평가일로 연율 변동성을 만들지 않는다. 현재 시연에서는 기록 대기 카드가 나온다. CORE의 위험 좌표는 API에 없으므로 산점도에 추가하지 않았다. 관측 MDD는 보이지만 위험 순위 보류는 유지한다.

사용자 요청과 구현은 AI가 수행했고, 실제 테스트 실행과 원장 수치 대조·브라우저 캡처로 검증했다.

## 실제 검증

| 검사 | 결과 |
| --- | --- |
| 원장 비교 API 회귀 | 18개 통과. 내부 낙폭·결측·단일 기록·CORE 누락·소유권·테마별 분모 포함 |
| 전체 백엔드 `python -m pytest -q` | 597개 통과, 폐기용 PostgreSQL 환경을 요구하는 28개 건너뜀 |
| 전체 프론트 `npm test` | 78개 통과 |
| `NEXT_DIST_DIR=.next-ledger-ranking-build npm run build` | production 빌드·타입 검사 통과 |
| Chrome 데스크톱 1440 / 모바일 390 | 두 흐름 통과. 필터·참여자·위험 순위 보류·접기·새로고침·기존 demo 화면 확인 |
| 원래 코드 `3419ca1`과 대조 | 복사된 같은 DB에서 원래 비교 서비스를 실행해 기준 응답 생성. 15명 각각의 metrics·rank·관측 수·series·quality·metric_quality·관측 범위와 전체 dates가 모두 동일 |

대표 계정은 `capstone03@example.com`이다. 공통 기간은 2026-09-16~10-02, 유효 평가 11개, 수익률 +0.21%, CORE +0.19%, 차이 +0.02%p, 관측 MDD -2.50%, 수익률 순위 11/15다. 9/24·25의 공백과 실제 forward 관측 0건은 유지한다. 현재 확정 구성을 과거 가격에 적용한 모의실험이며 실제 운용 실적이 아니다.

## 로컬 확인·재실행

미리보기: `http://127.0.0.1:3111/ranking` / 별도 API: `http://127.0.0.1:8111`.

원본 시연의 인증·설계·재생 SQLite를 읽기 전용 연결로 일관되게 복사했다. 무결성 검사와 FK 검사도 통과했다. 시연을 다시 재생하거나 가격을 수정하지 않았다. 새 서버는 복사본만 사용한다.

- 코드: 이 브랜치 `feat/ledger-ranking-presentation`.
- 데이터: `/private/tmp/robo-ledger-ranking-preview-w9wfgv2b`.
- 계정: 위 디렉터리 `accounts.json`의 기존 시연 계정. 비밀번호는 Git·로그에 넣지 않는다.
- 실행 기록·기준 응답·캡처: `.work/ledger-ranking-ui/` (Git 제외).

코드 디렉터리에서 서버를 재실행한다.

```bash
.venv/bin/python scripts/competition_replay.py serve --directory /private/tmp/robo-ledger-ranking-preview-w9wfgv2b
```

브라우저 회귀는 web 디렉터리에서 실행한다. `E2E_LEDGER_BASELINE`은 원래 API 응답을 대조할 때만 설정한다. 계정 파일을 가진 격리 시연 환경이 필요하다.

```bash
E2E_REPLAY_DIR=/private/tmp/robo-ledger-ranking-preview-w9wfgv2b \
E2E_LEDGER_BASELINE=../.work/ledger-ranking-ui/baseline.json \
npx playwright test --config playwright.ledger-ranking.config.ts
```

## 반영 시 주의할 범위

프론트와 비교 API의 추가 필드를 함께 반영한다. 이전 API와 기존 demo 입력도 호환되지만, 다른 순위 기준에서도 수익률 순위를 유지하려면 `return_rank`가 필요하다. 이번 작업은 로컬 커밋까지만 진행하며 push·PR·병합·배포는 하지 않았다. 이미 별도로 진행된 내부 관리자·자동 가격 수집 변경은 이번 기준 브랜치에 통합하지 않았다.
