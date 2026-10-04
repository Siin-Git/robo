# 15명 로컬 경쟁 시연 · 과거 가격 재생

## 목적과 완료 범위

고객이 확정한 서로 다른 위험도·테마 구성을 동일 자금·공통 기간으로 비교하는
로컬 시연이다. `feat/shared-competition-start`의 `dff6a58`을 그대로 이어받았다.
새 Competition 모델이나 금융 계산기는 만들지 않았다. 완료 기준은 15명 개인 및
CORE 계좌에 기존 주문→모의체결→보유·현금→NAV 엔진 기록을 만들고 기존 성과,
기여도, CORE 비교, 랭킹 화면에서 일치하는 값을 확인하는 것이다.

운영 bootstrap/T0 예약, 기존 3073 앱·예약 변경, 병합/배포, PR #12 수정,
가격 문제 수정, 새로운 시장/안전자산 기준과 개별 기업 추적 개발은 제외했다.
사용자 구성을 시연 목적으로 확정하는 대상은 새 로컬 계정뿐이다.

## 저장소와 원본 보존

- 개인 배포 저장소 `MinchoLover/robo`, 기본/PR 대상 `release/public-operation`:
  확인 시 `b6add639f1f5248b19fcc32a124529d7cbcc849b`.
- 팀 `Siin-Git/robo` develop 및 개인 develop: `250f315`. 별개 기준이며 임의 병합하지 않았다.
- GitHub의 마지막 Production 프론트 deployment도 `b6add63`. Render의 실제 실행 커밋은
  현재 접근 가능한 워크스페이스로 확인할 수 없다. 이 변경을 운영 적용으로 보고하지 않는다.
- `.work/competition-replay`, `feat/competition-replay`에서 작업했다. release에는 기존
  원장 성과/기여도/랭킹과 전략 구성 자료 조회가 이미 포함되어 추가 통합은 필요 없었다.
- 모든 DB·원본 가격·계정 파일·로그·캡처는 저장소 밖의 private 임시 디렉터리에 있다.
  기존 root/nested 체크아웃, 다른 worktree, 운영 데이터, 3073/8073 프로세스는 유지한다.

리뷰 브랜치 푸시가 배포를 유발하지 않도록 루트와 `web/vercel.json`의
`git.deploymentEnabled`에서 **feat/competition-replay만 false**로 지정했다.
다른 브랜치의 기본 동작/production 설정을 바꾸지 않는다.
[Vercel 공식 Git configuration](https://vercel.com/docs/project-configuration/git-configuration)의
브랜치별 설정을 사용하며 provider 계정 설정/실제 배포 명령은 실행하지 않는다.
최초 push에는 별도 루트 프로젝트 `Vercel – robo`가 자동 Preview를 시도해 실패했다.
웹 프로젝트만 설정한 것으로는 다른 Root Directory 프로젝트를 차단하지 못했으므로
루트에도 같은 브랜치 규칙을 추가했다. Production `robo-paper-web`의 `b6add63`은 유지된다.

## 설계 판단과 데이터 출처

`capstone_demo.db`는 시연 계정/DemoCohort/DemoSlot, `portfolio_design.db`는 실제 현재
시각의 최종 확정 판단을 보관한다. 확정은 기존 login/draft/preview/complete API를
거친다. 위험 수준 15개와 0–2개 테마, 월별/분기별을 다양하게 선택했다.

이 **새로운 로컬 설계 DB만** SQLite backup으로 `replay_ledger.db`에 복사한다.
기존 운영/합성 시연 DB를 복사하지 않는다. 판단 확정/효력일은 원본과 동일하다.
원본 설계에는 재생 주문/체결/NAV/T0가 없다. 변경 불가능한 `run.json`에 실행 UUID,
캡처 판단, 비중, 자금, 공통 날짜, 가격 출처·해시·비용·환율 관행을 보존한다.
`forward_state`에는 UUID/manifest 해시/진행 상태/계좌별 체크포인트만 추가한다.
스키마 추가는 없다.

조회는 `COMPETITION_REPLAY_DIR`가 있고 인증 DB가 같은 marked local SQLite인 경우만
`get_performance_db`의 읽기 전용 replay 세션을 사용한다. 정상 환경에서는 기존 설계
DB를 그대로 쓴다. 포트폴리오 변경/판단 상세/Revision/3·6개월 검토는 **원본 설계 DB**를
계속 사용하므로 재생으로 실제 추적 기간을 채우지 않는다. 봉인된 재생은 준비 시점 구성이다.
다시 설계한 내용은 새 재생 실행에서 반영해야 한다.

`execution_scope`는 이 임시 ledger의 **특정 연결 하나**에만 과거 실행 일정을 제공한다.
기존 `competition.policy`/`account_gate`를 재사용한다. 저장된 미래 로컬 T0와 원본
효력일을 과거로 바꾸지 않는다. 그 밖의 daily/직접 엔진 호출은
`REPLAY_SCOPED_EXECUTION_REQUIRED`로 차단한다. PostgreSQL/기존 로컬 운용은 허용하지 않는다.
재생 파일 잠금은 동시 bootstrap을 거부하고 daily는 가격 수집 전 차단한다.
체결 뒤 체크포인트 전 중단도 기존 초기 주문을 재사용하여 복구한다.

## 실제 재생 기록: 2026-10-04 확인

- 15/15 시연 준비·15/15 완료, 개인 15 + CORE 15계좌. 동일 초기 가상 자금 각각 1억원.
- 기간 **2026-09-16–2026-10-02**, **누락을 제외한 공통 관측일 10개**, 연속 10거래일이 아니다.
- 사용일: 9/16, 9/17, 9/21, 9/22, 9/23, 9/28, 9/29, 9/30, 10/1, 10/2.
- 원본 공백: 9/18 USDKRW; 9/24 한국주식/한국국채; 9/25 USDKRW/한국주식/한국국채.
  원인 코드는 `SOURCE_OBSERVATION_MISSING`: 원본에 해당 관측이 없음을 확인한 것이며
  휴장/공급자 장애 중 어느 원인인지는 단정하지 않는다. 초기 manifest에는 FX만 보이는
  주말 9/20·9/27도 제외 목록에 기록되어 있다. 주말 평가를 만들지 않았다.
- YahooChartProvider의 실제 일별 자료/환율. TIP도 이번 조회에서 수신했다. 누락 날짜를
  다른 날짜/이전 가격으로 채우지 않았다. 기존 align_daily_krw에 완전한 날짜만 전달했다.
- 기존 환율 관행: 미헤지 USD 자산은 USDKRW 곱, 한국 원화 자산은 원본,
  `HEDGED={us_treasury,tips}`는 원본 가격 level을 유지한다. 이것은 기존 헤지 대용
  가격 규칙이며 실제 원화 환헤지 ETF나 실증 증권 수량/주문을 재현한 것으로 발표하지 않는다.
- 기존 engine의 5bp 비용, 초기 시뮬레이션 주문과 첫 가용 종가 체결 후 보유.
  과거 정기 월간/주간 job 전체를 재생한 것은 아니다. 저장 주기 및 현재 상대 밴드 조회는
  기존 기능 그대로다. 20% 목표의 18%/22% 경계는 허용. KEEP/ADJUST는 구성 선택이지 주문 승인 아니다.
- 주문 **268**, 체결 **268**, 보유 평가 **2,680**, NAV **300**, 정렬된 가격/환율 **160**.
  모든 계좌·날짜에서 NAV=보유평가액+현금. NAV 행을 직접 생성한 것이 아니라 엔진을 실행했다.
- 대표 **capstone03@example.com**: 수익률 **−0.69516694%**, CORE **−1.05969012%**,
  차이 **+0.36452318%p**, 관측 MDD **−2.03842604%**. 기여도 합계와 수익률이 일치한다.
  공통 기간 개인 화면/랭킹 수치도 동일하다. 누적수익률 순위 15명은 제공한다.
- 내부 NAV를 공통 날짜 교집합으로 삭제하지 않는다. 표시 축 13개 평일 중 기록 없는 3일은
  null이고 선을 연결하지 않는다. MDD는 관측 값만 표시하고 공백 때문에 위험 순위는 보류한다.
  연율 변동성/TE/IR은 관측 부족으로 null이며 0으로 채우지 않는다.

## 복구와 forward 검증

PREPARED/RUNNING/INCOMPLETE/COMPLETE와 30계좌 날짜 coverage/회계 검증을 사용한다.
일부 참가자만 성공하거나 완성 후 기록이 손상되면 전체 완료/정상 랭킹을 표시하지 않는다.
재생 재실행, 준비 중 중단, 체결 후 NAV 전 중단, 체크포인트 후 중단·재개, 파일 잠금,
누락 가격 거부, manifest 변경 거부를 테스트했다. 서버 재시작 후에도 건수가 동일하다.

`FORWARD_VALIDATION`은 별도 marked **완료 재생 복사본**에만 허용한다. 자동 테스트에서만
미래 T0 시계·다음 날짜 가격 fixture를 사용했다. 기존 daily 엔진에 연결해 개인/CORE 초기
주문·체결 건수 유지, 다음 날짜 NAV +30, 동일 날짜 반복 중복 없음, 과거 기록 보존을 확인했다.
과거 체결을 실제 `first_execution_at`으로 등록하지 않는다.
원본 시연 DB에 미래 가격을 넣지 않았고 운영 forward 실행 성공도 아니다.

실제 forward 데이터와 이 재생을 한 그래프로 이어 붙이는 기능은 만들지 않았다.
재생 완료와 운영 전환 가능성 검증을 분리했다. 사용자가 운영 T0를 합의·예약하고 실운용
코드를 별도로 검토·적용할 때 실제 관측을 쌓아야 한다.

## 교수님 요구 대조

| 요구 | 기존 구현/연결 | 현재 한계 |
|---|---|---|
| 구성 선택 이유·성과·기여도 | `/portfolio`, `/dashboard`, `/ranking`; `onboarding_service`, `calculate_report`, 원장 조회 | 실제 시연은 현재 구성 과거 재생임을 표시. 선택 이유는 시연 문구, 투자 권고로 표현하지 않음 |
| 최초 판단과 Frontier 정보 보존 | `PortfolioDecision`, `decision_service.capture/serialize`, `/review`; Frontier ID/버전·기본/최종 비중·예상값·위험 비교·자료 해시 | 현재 모델로 과거 예상 재생성 없음. Frontier 두 점 화면은 기존 구성 조회를 재사용 |
| 종목별 이후 추적 | `PriceDaily`, `Holding`, `Trade`, `NavDaily`, 기여도: 선택 ETF/자산별 10개 실제 가격 관측과 평가 | ETF 내부 기업별 후속 가격 추적은 확인되지 않음. `/strategies`와 `strategy_service`는 기존 주도주/수출 구성 snapshot·연구 backtest 조회, 사용자 원장과 별도. 중복 개발하지 않음 |
| revision 검토·기록 | `/review`, `PortfolioChoice`, KEEP/ADJUST, 새 확정 판단의 previous_decision_id | 검토만으로 자동 변경 없음. 재생을 실제 예상↔실제/3·6개월에 사용하지 않음. 같은 기간/정의의 예상 수치 비교는 기존 제한 유지 |

## 운영 참가자 확인

기존 Actions `daily-forward`를 **dry_run=true**로 실행했다. 실행 `37208198285`의
읽기 전용 인벤토리: 인증 사용자/참가자 15, 설계 사용자 1·개인/CORE 2계좌·판단 3버전
(확정 사용자 1명), pending 포함 주문 8, 체결/holdings/NAV 0. 로컬 15/15와 별개이다.
추가 Actions **37211864102**(이번 브랜치, dry_run=true)에서 기존 공동 gate로 슬롯 확인/
계좌 소유권/불변 판단 연결까지 조회해 **READY 1/15, NOT_READY, PARTICIPANTS_NOT_READY,
T0 null**을 확인했다. 나머지 14명을 임의 확정하지 않았다.
주문/체결/평가/job/T0를 쓰지 않는 dry-run이다. 실제 Render DB와 Actions DB가
같은지 및 Render 커밋은 해당 운영 workspace 접근이 필요하다. secret 값을 요청하지 않는다.

## 검증과 명령

Python 3.11.15, 별도 PostgreSQL 18.6와 SQLite: 최종 `pytest tests --ignore=tests/backup -q`
**576 passed / 0 failed / 0 skipped**. 기존 CI와 동일 범위이며 backup 테스트/PR12는 수정하지 않았다.
프론트 **74 passed (17 files)**, production build(타입 검사 포함) 통과.
별도 lint 명령은 없으며 Next build 검사를 사용했다. 설치된 잠금파일 기반 node_modules와
기존 venv를 재사용했으며 의존성 변경은 없다.
브라우저 테스트: 대표03 로그인→포트폴리오/Frontier→보유·현금/주문·체결→성과/기여도→
CORE/15명랭킹→공통기간 수치→위험순위 보류→판단 검토→새로고침/재로그인,
1440×1000·390×844 **2 passed**, 런타임 오류/페이지 수평 잘림 없음.

worktree에서 실행한다 (`.venv`/`web/node_modules`는 기존 환경 링크 또는 설치 필요).

```sh
# 지금 실행된 시연: 기존 DB와 계정·가격을 그대로 재사용
.venv/bin/python scripts/competition_replay.py status --directory /private/tmp/robo-competition-replay-f8q138c4
.venv/bin/python scripts/competition_replay.py run --directory /private/tmp/robo-competition-replay-f8q138c4
.venv/bin/python scripts/competition_replay.py stop --directory /private/tmp/robo-competition-replay-f8q138c4
.venv/bin/python scripts/competition_replay.py serve --directory /private/tmp/robo-competition-replay-f8q138c4

# 독립적인 새 시연: 반드시 존재하지 않는 임시 디렉터리, 사용하지 않는 포트
.venv/bin/python scripts/competition_replay.py init --directory /private/tmp/robo-replay-new --port 3098 --api-port 8098
.venv/bin/python scripts/competition_replay.py fetch --directory /private/tmp/robo-replay-new
.venv/bin/python scripts/competition_replay.py prepare --directory /private/tmp/robo-replay-new
.venv/bin/python scripts/competition_replay.py run --directory /private/tmp/robo-replay-new
.venv/bin/python scripts/competition_replay.py serve --directory /private/tmp/robo-replay-new

# 실행 중인 별도 시연 서버에 브라우저 검증 (web 디렉터리)
E2E_REPLAY_DIR=/private/tmp/robo-competition-replay-f8q138c4 E2E_REPLAY_OUTPUT=/private/tmp/robo-competition-replay-f8q138c4/screens npm exec playwright -- test --config playwright.replay.config.ts --reporter=line
```

fetch는 봉인된 run 가격을 덮어쓰지 않는다. 실패 시 `price-failures.json`의 자산/원인을
확인한다. DB/manifest는 수동 편집하지 않는다. 서버 stop은 자신의 process group/cwd만
확인하며 다른 서버를 종료하지 않는다. 로그: 시연 디렉터리 `logs/api.log`, `logs/web.log`.
임시 디렉터리는 OS 정리 대상이라 영구 운영 저장소가 아니다. 시연 보존이 필요하면
서버 종료 후 이 **시연 디렉터리 전체**를 별도 비공개 위치에 보관한다. 기존 실제 운용 DB는 별개다.

## 돌아와서 볼 5분 시연

접속 `http://127.0.0.1:3097/dashboard`; 대표는 `capstone03@example.com`.
이미 열어둔 시연 브라우저는 참가자01로 로그인되어 있다. 참가자03 비밀번호는
시연 디렉터리 `accounts.md` 또는 `accounts.json`에서만 확인한다. 저장소/PR에는 없다.

1. **0:00–0:30** 상단 15/15와 기간/출처 안내: 현재 구성을 과거에 적용한 별도 모의실험.
2. **0:30–1:15** 내 포트폴리오: 위험·로봇 테마·확정 주기, Frontier 전/후 두 점, 구성 변화.
3. **1:15–2:15** 대시보드: 보유·현금·NAV 원화 합계, 주문/체결 History, 누적 그래프.
4. **2:15–3:00** 개별 자산 기여도: 합계가 전체 수익률과 일치, CORE 기준과 차이 확인.
5. **3:00–4:00** 참여자 비교: 동일 기간 기준100 그래프·15명 수익률 순위;
   MDD 선택 시 공백 때문에 순위 대기, 연율 변동성도 보류. 결측은 null로 끊긴다.
6. **4:00–5:00** 최초 예상·실제 검토: 오늘 확정/미래 효력일·원본 이유/버전,
   실제 평가 대기 및 3·6개월 미도달. 필요하면 유지/조정 UI를 설명하되 재확정하지 않는다.
   마무리: 실제 forward는 T0 이후 별도로 쌓이며 지금 결과와 이어붙여 장기 실적으로 발표하지 않는다.

핵심 캡처는 시연 디렉터리 `screens/portfolio-1440.png`, `dashboard-1440.png`,
`ranking-1440.png`, `review-1440.png`와 동일 이름 `-390.png`에 저장했다.
`verified-1440.json`/`verified-390.json`에 기간·수치·15명 랭킹/기여도 검사 결과가 있다.
AI 구현 결과를 명령·테스트·실제 브라우저 렌더와 대조한 증거이며 운영 실행 증거가 아니다.
