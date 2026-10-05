# 내부 판단·자산 추적 통합 — 2026-10-05

> 2026-10-05 통합 상태: 이 기능은 기존 Draft PR #1에 함께 반영한다. 아래는 해당 기능의 최초 작업 기록이며, 현재 통합 검증과 배포 범위는 [CAPSTONE_UNIFIED_HANDOFF.md](CAPSTONE_UNIFIED_HANDOFF.md)를 기준으로 확인한다.

## 기준과 재사용한 구현

고정 중간점검 시연은 `/private/tmp/robo-session-dates-20261005`의 `3419ca1479ded66f3dfd513d4b47e3090f94362d`, 프론트 3099이다. 이 작업은 별도 `/private/tmp/robo-internal-tracking-integration-20261005`, 브랜치 `integration/internal-tracking-demo`에서 진행했다. 3099 코드·DB·백업은 수정하지 않았다.

기존 `/private/tmp/robo-decision-asset-tracking-20261004`의 `6cd16d8`(API), `e8298c8`(화면), `4aca339`(인수 문서)을 먼저 확인했다. 해당 구현을 재사용하고 최신 Yahoo 세션 날짜·공동 시작 account_gate·과거 재생 구분·성과/기여도/랭킹·상세 설명 토글을 보존했다. 기존 기능을 새 금융 계산기로 대체하지 않았다. 기존 브랜치에 함께 있던 새로운 WEIGHT_DRIFT 알림과 운용 이벤트 표시 확장은 이번에 포함하지 않았다.

## 교수님 원문과 현재 연결

원문: `/Users/jeongminchan/.codex/attachments/8fbb9aa6-8a92-4fd8-b06a-64078fb3505b/붙여넣은 텍스트.txt`.
00:00의 최초 판단 보관·자산별 이후 추적·3/6개월 내부 검토와 03:00, 32:00–34:00의 고객 설명을 구분했다. 자동 전사에서 불확실한 문장을 금융 규칙으로 만들지 않았다. ETF 안의 모든 기업 추적은 이번 필수 범위로 확대하지 않았다.

| 요구 | 현재 통합 위치·상태 | 실제 데이터의 한계 |
|---|---|---|
| 최초 판단·Frontier 보존 | `decision_service.capture` → `portfolio_decisions.provenance_json.internal_tracking`; 신규 확정 당시 제공된 Frontier 좌표 전부와 자산별 연간 예상값·모형/자료 근거를 보관. 관리자 `/admin/tracking`에서 확인 | 새 로컬 확정은 좌표 50개. 15명 기존 판단에는 새 스냅샷이 없으므로 소급 생성하지 않음. 고객 Portfolio의 현재 곡선은 보관 곡선과 구분 |
| 편입 자산별 이후 추적 | `internal_tracking_service.report` → 기존 `prices_daily`, 원장 기여도 계산기; 관리자 자산 선택·결측 그래프·3/6개월 상태 | 확정 효력일 이후 저장 가격/평가만 읽음. 이번 로컬 원본 판단의 실제 운용 관측은 0개; 과거 재생 11개로 채우지 않음 |
| 내부 Revision 검토·기록 | 관리자 POST reviews → `events`의 `INTERNAL_ASSET_REVIEW`; 방향·근거·검토자·시각·당시 관측 저장, 이력 조회 | 검토는 기록이며 모형·판단·비중·주문을 자동 변경하지 않음. 예상↔실제 차이는 정의 미합의로 NOT_COMPARABLE |
| 고객 구성 이유·성과·기여도 | 기존 Portfolio/Frontier·대시보드·기여도·랭킹 재사용; 고객용 판단 review는 기존 범위로 보존 | 3103의 15명 성과는 실제 가격을 적용한 과거 모의실험. 실제 forward 및 3/6개월 실적과 구분 |
| 사용자·관리자 권한 | `require_admin`, `get_admin_design_db`, CSRF; 고객 serialize에서 internal_tracking 제거, 고객 alerts/성과에 내부 메모 비노출 | 실제 배포에서 관리자 역할 부여와 접근 검증은 미실행 |

## 저장·조회 계약

- `GET /api/v1/admin/tracking`: 운용/설계 DB의 판단 목록. 관리자에게 참가자 설정을 강제로 만들지 않는다.
- `GET /api/v1/admin/tracking/{decision_id}`: 최초 스냅샷, 자산별 가격 변화, 원장 기여도, 관측 구간, 3/6개월 상태, 내부 검토 이력.
- `POST /api/v1/admin/tracking/{decision_id}/reviews`: CSRF와 관리자 권한 필수. 서버가 검토자 ID를 지정한다. 같은 request_key/내용은 기존 기록 반환, 다른 내용은 409. 판단 외 자산은 422.
- 신규 확정은 기존 완료 API를 사용한다. 기존 판단 UPDATE/DELETE 방지와 버전 연결을 유지한다. 저장하지 않은 최초 예상값을 현재 모형으로 보충하지 않는다.
- 연간 예상 단위는 `fraction_per_year`, 기간 `1Y`. 기존 예상 수익·공분산 계산을 사용한다. 테마 예상 수익은 조달원 주식 예상값을 계승하며 독립적 테마 예측으로 표시하지 않는다.
- 관측 시작은 해당 판단 효력일, 종료는 다음 판단 효력일 또는 한국 날짜 조회일+1 중 먼저인 날짜(미포함). 미래 대기 판단이 현재 판단 기록을 지우지 않는다.
- 가격 수준은 저장된 KRW 가격의 비용 제외 변화, 기여도는 모의운용 원장 계산 결과이다. 현금 가격 수익률·기록 부족 통계를 만들지 않고 결측은 null로 유지한다.
- 3/6개월 가격 추적은 첫 유효 가격 관측일부터, 가격이 없으면 효력일 기준 잠정 일정만 표시한다. 기간이 지나도 예상 기간/단위/정의 합의가 없으면 차이 계산은 계속 보류한다.
- 관리자는 원본 설계/forward DB를 읽는다. `replay_ledger.db`는 별도 대시보드용이며 이 보고서로 잘못 전달돼도 `REPLAY_NOT_FORWARD_OBSERVATIONS`(409)로 차단한다. 관리자 화면에는 과거 재생 안내/평가 수를 실제 추적처럼 보여주지 않는다.
- 검토 이력은 API에서 추가만 가능하고 수정·삭제 API는 없다. 모든 Event에 DB 불변 트리거를 추가한 것은 아니다. 새 DB 마이그레이션은 없다.
- 새 수집기·예약 실행은 등록하지 않았다. 이후 가격·체결·평가는 기존 일간 운용 엔진이 저장해야 한다. 보고서 자체는 데이터를 생성하지 않는다.

## 별도 로컬 화면과 데이터

주소: **http://127.0.0.1:3103/admin/tracking**, API 8103.
데이터: `/private/tmp/robo-internal-tracking-local-20261005/` (비공개, Git 제외).

- 고정 3099의 백업에서 별도 복사한 15명·개인/CORE 30계좌, 9/16–10/2 공통 관측 11개를 보존했다. 수정 후 P003 +0.21127061%, CORE +0.18845140%, 순위 11/15, NAV 330행을 유지한다.
- **LOCAL VALIDATION ONLY** 관리자 `tracking-admin@example.com`과 신규 확정 검증 계정 `tracking-participant@example.com`을 이 복사본에만 추가했다. 15명 경쟁 참가자가 아니며 운영 READY에 합산하지 않는다.
- 신규 계정은 실제 현재 시각으로 기존 위험도/테마/확정 API를 통과했다. 과거 확정일·효력일·T0를 만들지 않았다. 가격·체결·평가를 합성 생성하지 않았다.
- 관리자에서 최신 검증 판단을 선택하면 최초 Frontier 50좌표와 자산별 예상값, 실제 평가 0건, 기간 미도달, 저장한 검토 이력이 보인다. 기존 참가자 판단은 최초 자산값 미기록 상태다.
- 비밀번호는 `internal-accounts.json`/`internal-accounts.md`, 기존 15명은 `accounts.json`/`accounts.md`에만 있다. 채팅·Git·PR에 넣지 않는다.

직접 확인 순서: 관리자 로그인 → Admin의 내부 판단 추적 → 최신 검증 판단 → Frontier 좌표 펼치기 → 자산별 예상/관측 상태 → 검토 방향·근거 저장 → 새로고침. 기존 참가자로 다시 로그인하면 관리자 API 403이며 대시보드의 과거 모의실험은 계속 표시된다.

서버 재시작(이 환경의 서버만 제어):

```sh
cd /private/tmp/robo-internal-tracking-integration-20261005
.venv/bin/python scripts/competition_replay.py stop --directory /private/tmp/robo-internal-tracking-local-20261005
.venv/bin/python scripts/competition_replay.py serve --directory /private/tmp/robo-internal-tracking-local-20261005
```

DB를 지우거나 prepare/bootstrap을 다시 실행할 필요가 없다. 런처는 같은 DB와 계정·메모를 재사용한다. 로그는 데이터 디렉터리의 `logs/api.log`, `logs/web.log`에 있다.

재시작 전 3개 SQLite DB를 일관된 backup API로 `backup-before-restart/`에 보관하고 integrity_check를 통과했다. 재시작 후 관리자 로그인 조회에서 같은 Frontier 50좌표·검증용 검토 6건·판단 16건(기존 15+별도 검증 1)을 확인했다. 판단/Event 전체 행은 백업과 일치하며 원본 설계 DB의 주문·체결·보유·NAV는 모두 0, 별도 재생 NAV는 330행 그대로다. 이 수치는 운영 참가자 READY 수나 실제 운용 성공을 뜻하지 않는다.

기능 커밋: `db2dad0` (API/보관/검증), `29db875` (관리자 화면/브라우저 회귀). 이후 문서 커밋은 이 인수 결과만 기록한다. 최종 로컬 HEAD는 `git rev-parse HEAD`로 확인한다.

## 검증과 재현

Python 3.11.15, 폐기용 PostgreSQL 18.6의 독립 UTF-8 DB에서 기존 CI 범위 `python -m pytest tests --ignore=tests/backup -q`: **599 passed, 0 failed, 0 skipped**, 23 기존 의존성 경고. 백업 PR #12의 별도 테스트/워크플로는 수정하지 않았다. 원격 CI·배포 성공으로 보고하지 않는다.
관련 API/DB/공동 시작/재생 테스트: **47 passed**. Frontier 미기록·모형 변경 후 고정값·일반 API 전체 비노출·0/1건·현금·가격 결측·KST/후속 판단 경계·리뷰 중복/충돌·CSRF·사용자/관리자 분리·PostgreSQL 4개 동시 요청 1개 저장·결정/목표/주문/체결/보유/NAV 불변·새 세션 재조회·replay 차단을 검증했다.

최종 프론트 **81 passed / 19 files**, 프로덕션 빌드·린트·타입 검사 통과. 브라우저는 Chrome 데스크톱 1440px/모바일 390px의 기존 15명 흐름 **2 passed**, 관리자 저장·새로고침·재로그인·일반 사용자 403·가로 잘림 검사 **2 passed**. 캡처는 로컬 데이터 디렉터리의 `replay-screens/`, `tracking-screens/`에 있으며 운영 데이터 증거가 아니다.

최초 전체 검사에서 SQL_ASCII로 만든 폐기용 PG가 bytes를 반환해 발생한 16개 실패는 UTF-8 테스트 DB로 재생성해 해결했다. 추가 검증 코드의 모형 monkeypatch 범위, 존재하지 않는 alert 경로, 브라우저 중복 텍스트 locator도 수정했다. 최종 검사에서 기존 테스트를 삭제·skip하지 않았다.

재현 명령(폐기용 TEST_DATABASE_URL/TEST_AUTH_DATABASE_URL/TEST_DESIGN_DATABASE_URL만 사용):

```sh
python -m pytest tests --ignore=tests/backup -q
cd web
npm test
NEXT_DIST_DIR=.next-integration-tracking-build npm run build
E2E_TRACKING_DIR=/private/tmp/robo-internal-tracking-local-20261005 \
E2E_TRACKING_URL=http://127.0.0.1:3103 \
E2E_TRACKING_OUTPUT=/private/tmp/robo-internal-tracking-local-20261005/tracking-screens \
npm exec playwright -- test --config playwright.internal-tracking.config.ts --reporter=line
```

## 남은 작업·운영 구분

현재 추가 기능은 로컬 통합·검증·커밋 범위다. 3099 고정 시연, 3073 실제 로컬 앱·데이터, 운영 DB·공동 T0·자동운용 예약·백업 PR #12를 변경하지 않았다. 이번 브랜치를 푸시·병합·배포하지 않는다.

이후 승인된 배포에서 API/프론트를 함께 반영하고 실제 관리자 역할·인증/운용 DB 연결·신규 확정 스냅샷·일간 가격/평가 적립을 확인해야 한다. 기존 판단을 진짜 최초 예상으로 소급 보충할 수 없다. 실제 forward 기록과 3/6개월 기간은 앞으로 쌓여야 하며 기간 통과만으로 예상↔실제 비교 정의가 완성되지 않는다. 시장/안전자산 기준, 주도주·수출 모델, ETF 내부 모든 기업 추적은 이 통합으로 구현됐다고 보고하지 않는다.
