# 운용 기록 배치 운영

매일 종가를 받아 사용자별 보유·현금·수익률을 기록하는 배치를 어떻게 돌리고,
뭐가 깨졌을 때 어떻게 알아채고 고치는지 적는다. 백엔드 A(규영) 담당 범위다.

담당이 바뀌어도 이 문서만 보고 배치를 운영할 수 있는 것이 목표다.

> 2026-09-29 기준. 월간 리밸런싱 실제 실행과 배포 환경 검증은 아직 안 끝났다.
> 해당 절에 **[미검증]** 으로 표시했다.

---

## 1. 실행 환경

### 환경변수는 항상 두 줄 세트

```powershell
$env:APP_PROFILE="local"
$env:CAPSTONE_DEMO="1"
```

`.env.local` 에 값이 있더라도 **명시적으로 주는 습관을 들인다.** 실제로 이것을
빼먹어 같은 명령이 다른 DB 를 가리킨 적이 있다(2026-09-28).

### 배너를 먼저 읽는다

모든 forward CLI 는 시작할 때 배너를 찍는다. **다음 명령을 치기 전에 네 줄을
눈으로 확인한다.**

```
=====================================
PROFILE: LOCAL
MODE: CAPSTONE (design workspace)
BACKEND: SQLITE
DATABASE: data\portfolio_design.db
=====================================
```

| 줄 | 의미 |
|---|---|
| `PROFILE` | `local`/`demo`/`validation`/`live`. 운용 DB 를 가른다 |
| `MODE` | `CAPSTONE` 이면 설계 DB(대시보드가 읽는 곳)에 기록한다 |
| `BACKEND` | `SQLITE` / `POSTGRES` |
| `DATABASE` | 실제 기록 대상. 이게 예상과 다르면 **바로 멈춘다** |

### DB 두 개를 구분한다

| 파일 | 내용 | 누가 쓰나 |
|---|---|---|
| `data/capstone_demo.db` | 13명 로그인 계정, 고정 비교 시연 데이터(가상 NAV) | API 인증 |
| `data/portfolio_design.db` | **실제 forward 운용 기록** | forward 엔진 + 대시보드 |

프론트는 `/dashboard` 가 실제 기록, `?source=demo` 가 비교 시연 데이터다.
둘은 섞이지 않는다.

랩미팅 런처(`scripts/start_lab.py`)를 쓰면 `CAPSTONE_DATA_DIR` 가
`.work/lab-meeting` 으로 바뀐다. 그 모드에서 CLI 를 돌릴 때는 같은 값을 줘야
같은 DB 를 본다.

```powershell
$env:CAPSTONE_DATA_DIR="$PWD\.work\lab-meeting"
```

---

## 2. 안전 실행 시간대 — 중요

**장이 열려 있는 동안 가격을 받으면 안 된다.**

야후는 장중에도 그날 바를 돌려준다. 그 값이 저장되면 `refresh_live` 의 증분
규칙(시작점 = 마지막 보유일 + 1일) 때문에 **같은 날짜를 다시 받아오지 않는다.**
잠정가가 종가로 굳고 스스로 고쳐지지 않는다.

| 시간(KST) | 상태 |
|---|---|
| 06:00 ~ 08:59 | **안전** — 미국 종가 확정 후, 한국 개장 전 |
| 09:00 ~ 15:30 | 한국 장중 — 금지 |
| 15:31 ~ 22:29 | **안전** — 한국 종가 확정 후, 미국 개장 전 |
| 22:30 ~ 05:00 | 미국 장중 — 금지 |

자동 실행은 07:10 / 17:10 이라 안전하다. **수동 실행만 주의하면 된다.**

읽기 전용 명령(`dev_ledger_report.py`, 로그 확인, `--dry-run`)은 언제 돌려도
상관없다. 가격을 받아오지 않는다.

### 실제로 한 번 발생했다 (2026-09-29)

22:36 에 배치를 수동 실행했다. 미국 장이 22:30 에 열린 뒤였다. 미국 자산 16개의
09-29 "종가"가 장 시작 6분 뒤 가격으로 기록됐고, NAV 가 `-0.25%` 로 계산됐다.

두 결함이 겹쳐서 일어났다.

1. 작업 레지스트리가 그날 세 번째 실행을 막지 못했다(§6 참조, 수정 완료)
2. 장중 가격을 거르는 코드 가드가 없다(**미해결**, §8 참조)

`scripts/dev_repair_intraday.py` 로 복구했다. 발견 경로는
`dev_ledger_report.py` 의 `last nav` 날짜가 예상과 다른 것이었다.

---

## 3. 매일 무슨 일이 일어나는가

### 자동 실행

Windows 작업 스케줄러의 `robo-forward-daily` 태스크가 `scripts/run_daily_task.bat`
를 07:10 과 17:10 에 부른다. 노트북이 꺼져 있었으면 깨어난 직후 실행된다
(`-StartWhenAvailable`).

배치가 하는 일은 순서대로 이렇다.

1. `run_daily` — 가격 갱신 → 주문 생성 → 체결 → 평가
2. **매월 1일이면** `run_monthly --dry-run` 을 찍고 이어서 `run_monthly` 실행
3. `dev_ledger_report.py` — 결과 요약

모두 같은 로그에 누적된다: `logs/forward_daily.log` (gitignore 대상).

월간을 같은 파일에 넣은 이유는 **순서 보장** 때문이다. 월간 결정은 전날 종가가
필요한데, 트리거를 둘로 나누면 노트북이 깨어날 때 둘이 밀려 실행되면서 순서가
보장되지 않는다.

### 하루 한 번만 수집한다

`scheduled_jobs` 테이블이 `(job_type, scheduled_for)` 단위로 성공 기록을 남긴다.
그날 이미 성공했으면 이후 실행은 건너뛴다. 실패한 날은 재시도된다.

그래서 17:10 실행은 **아침 실행이 실패했을 때의 재시도**이지, 두 번째 수집이
아니다. 아침에 성공했으면 저녁은 `daily job skipped` 로 끝난다.

### 미실행 날짜는 다음 실행이 따라잡는다

`refresh_live` 는 자산별로 마지막 보유일 다음부터 받아온다. 노트북이 이틀 꺼져
있었으면 다음 실행이 이틀치를 한 번에 채운다. `run_daily` 는 멱등이라 여러 번
돌려도 행이 늘지 않는다.

---

## 4. 상태 확인

### 매일 아침 한 줄

```powershell
Get-Content logs\forward_daily.log -Tail 60
```

### 참가자별 기록과 독립성 점검

```powershell
$env:APP_PROFILE="local"; $env:CAPSTONE_DEMO="1"
.venv\Scripts\python.exe scripts\dev_ledger_report.py
```

읽기 전용이다. `[4] 독립성 점검` 이 통과하면 모든 기록이 참가자에 정확히 하나씩
연결돼 있다는 뜻이다. 다른 DB 를 보려면 `--db data\capstone_demo.db`.

### 가격 수집이 가능한 상태인지

```powershell
.venv\Scripts\python.exe scripts\dev_check_live_prices.py --days 7
```

읽기 전용이다. 자산별 커버리지, 티커 맵, 야후 조회 성공 여부를 찍는다.
티커는 19개(코어 9 + FX + 테마 9)가 정상이다.

### 특정 줄만 뽑기

```powershell
Select-String -Path logs\forward_daily.log -Pattern "RUN START","refresh:","STATUS:","EXIT=" | Select-Object -Last 8
```

---

## 5. 출력 읽는 법

### STATUS

| 값 | 뜻 | 대응 |
|---|---|---|
| `PASS` | 정상 | 없음 |
| `PARTIAL` | 일부 계좌가 아직 평가되지 않음 | **실패가 아니다.** 체결 전이거나 가격이 없는 상태. 종료 코드 0 |
| `FAIL` | 불변식 위반(회계 항등식, 액티브 슬리브 초과 등) | 즉시 확인. 종료 코드 1 |

`PARTIAL` 에 `awaiting first execution (no NAV yet)` 가 붙는 것은 체결 전이라
NAV 앵커를 만들지 않는 정상 동작이다. 체결 전에 성과를 백필하지 않는다.

### refresh

```
refresh: {'new_points': 18, 'stale': [], 'asof': '2026-09-29'}
```

| 필드 | 뜻 |
|---|---|
| `new_points` | 새로 저장된 가격 행 수. 자산 수 × 거래일 수 |
| `stale` | **조회가 예외로 끝난 자산.** 장애가 아닐 수 있다 |
| `asof` | 실행 기준일(벽시계) |

**`stale` 을 장애로 읽지 마라.** 조회 구간에 거래일이 하나도 없으면(연휴 등)
야후가 빈 시리즈를 주고 예외가 난다. 실제 문제는 `events` 의 `PRICE_REFRESH`
이벤트에 있는 `stale_assets` 다 — 마지막 가격이 `stale_price_days`(14일)를
넘긴 자산만 들어간다.

실제 사례: 2026-09-28 아침에 `stale: ['korea_equity', 'korea_treasury']` 가
나왔다. 추석 연휴(09-24~26)로 한국 거래일이 없었을 뿐이고 마지막 가격은 09-23
이라 밀린 것도 아니었다.

### 평가 기준일

```
valuated 26 accounts at 2026-09-28
```

**실행일이 아니라 마지막으로 종가가 확정된 날**이다. 시계가 아니라 데이터가
기준이라는 원칙이 여기서 드러난다.

---

## 6. 실패 시 대처

### 가격 수집이 실패했다

`events` 에 `PRICE_REFRESH_FAILED` 가 남고 `/me/alerts` 에 경고로 나간다.
전 사용자에게 보인다(운용이 멈추면 모두의 문제다).

```powershell
.venv\Scripts\python.exe scripts\dev_check_live_prices.py --days 7
```

`[4] 판정` 을 본다. 야후가 일시적으로 막힌 거면 다음 실행에서 따라잡는다.
그날 작업은 실패로 기록되므로 **17:10 재시도가 자동으로 돈다.**

### 배치가 아예 안 돌았다

노트북이 꺼져 있었으면 기록 자체가 없다. 이건 이벤트로 잡히지 않는다.
`dev_ledger_report.py` 의 `last nav` 날짜나 `/me/ledger/status` 의
`data_freshness` 로 알아챈다.

```powershell
Get-ScheduledTask -TaskName "robo-forward-daily" | Get-ScheduledTaskInfo
```

`LastTaskResult` 가 0 이 아니거나 `LastRunTime` 이 오래됐으면 수동으로 한 번
돌린다(§2 시간대 확인).

### 장중 가격이 들어갔다

증상: 자산별 마지막 가격일이 장 마감 전인데 오늘 날짜로 찍혀 있다.

```powershell
.venv\Scripts\python.exe -c "import sqlite3; c=sqlite3.connect('data/portfolio_design.db'); print(*c.execute('SELECT asset_id, MAX(date) FROM prices_daily GROUP BY asset_id ORDER BY 2 DESC, 1'), sep=chr(10))"
```

복구:

```powershell
copy data\portfolio_design.db data\portfolio_design.db.bak-before-repair
.venv\Scripts\python.exe scripts\dev_repair_intraday.py --date 2026-09-29 --market us
.venv\Scripts\python.exe scripts\dev_repair_intraday.py --date 2026-09-29 --market us --apply
```

`--apply` 없이 먼저 돌려 미리보기를 확인한다. 그 날짜에 **체결이 있으면**
수량과 현금이 잠정가로 계산됐다는 뜻이라 스크립트가 거부한다. 그 경우엔 체결까지
되돌릴지 먼저 판단해야 한다.

지운 뒤 다음 실행이 그 날짜부터 다시 받아온다. `events` 에
`INTRADAY_PRICES_REPAIRED` 로 기록이 남는다.

### 같은 날 배치가 여러 번 돌았다

`scheduled_jobs` 가 막는다. 뚫렸다면 버그다(2026-09-29 에 한 번 있었고 수정했다).

```powershell
.venv\Scripts\python.exe -c "import sqlite3; c=sqlite3.connect('data/portfolio_design.db'); print(*c.execute('SELECT scheduled_for, job_type, status, started_at FROM scheduled_jobs ORDER BY started_at DESC LIMIT 10'), sep=chr(10))"
```

한 날짜에 `success` 가 둘 이상이면 이상하다.

### 회계 항등식이 깨졌다 (`STATUS: FAIL`)

`Σweight + cash/nav = 1` 이 성립하지 않는다는 뜻이다. `valuate` 가 쓰기 전에
검사해서 `NAV_INCOMPLETE` 로 빠지므로 잘못된 행이 남지는 않는다.

원인은 대개 보유 행과 체결이 어긋난 경우다. 해당 계좌·날짜의
`holdings_daily`, `trades`, `nav_daily` 를 함께 본다.

### 테스트가 깨졌다

```powershell
pytest tests/forward tests/api -q
```

**환경변수를 켜둔 상태에서도 통과해야 한다.** 예전에 `test_frontier.py` 가
셸의 `CAPSTONE_DEMO=1` 때문에 깨진 적이 있고, 그건 테스트 쪽 결함이라 고쳤다.
비슷한 증상이 또 나오면 그 픽스처에 환경 정리가 빠진 것이다.

---

## 7. 테이블 — 원장이 만들어지는 순서

```
prices_daily  →  portfolio_targets  →  orders  →  trades  →  holdings_daily  →  nav_daily
```

| 테이블 | 한 행이 뜻하는 것 |
|---|---|
| `prices_daily` | 자산 하나의 하루 종가(원화 환산) |
| `portfolio_targets` | 계좌·효력일·종류당 목표 비중 **하나** |
| `orders` | 목표에 도달하기 위한 자산별 주문 |
| `trades` | 실제 체결. 가격·수량·비용 |
| `holdings_daily` | 계좌·날짜·자산의 보유 수량과 비중 |
| `nav_daily` | 계좌·날짜의 평가액, 현금, 수익률 |

보조 테이블 셋.

| 테이블 | 쓰임 |
|---|---|
| `events` | 무슨 일이 있었는지. append-only. `/me/alerts` 가 여기서 읽는다 |
| `scheduled_jobs` | 배치 실행 기록. 중복 실행 방지 |
| `forward_state` | 운용 시작 시각 등 생애주기 값 |

### 알아둬야 할 규칙

**효력일은 결정일의 다음 거래일이다.** 주문은 `effective_at` 이후 첫 거래일
종가에만 체결된다(`next_available_close`). 미래 가격을 쓰지 않는다는 뜻이고,
반대로 과거 종가에 체결하는 것도 막는다.

**목표는 계좌·효력일·종류당 한 행이다.** 배치를 다시 돌려도 덮어쓴다. 조회는
`effective_date DESC, created_at DESC, target_id DESC` 로 정렬해 동점에서도
결과가 흔들리지 않게 한다.

**보유 행은 그날 것을 통째로 다시 쓴다.** 전량 매도한 자산의 행이 남으면
`Σweight` 에 유령이 섞여 항등식이 깨진다.

**`__FX__` 는 `prices_daily` 에 저장되지 않는다.** 원화 환산용으로만 쓰이고
버려진다. 0행인 것이 정상이다.

### 백엔드 B(종언님) 에게

직접 쿼리하지 말고 API 를 쓰면 된다.

| 필요한 것 | 엔드포인트 |
|---|---|
| 내 운용 기록이 있는지, 최신인지 | `GET /api/v1/me/ledger/status` |
| 사용자 알림 | `GET /api/v1/me/alerts` |
| 내 포트폴리오 | `GET /api/v1/me/portfolio` |
| 기본 대비 개인화 비교 | `GET /api/v1/me/portfolio/summary` |

모두 로그인한 사용자의 `participant_id` 기준으로만 조회한다.

`status` 의 `data_freshness` 가 `OK`/`STALE`/`NO_DATA` 로 데이터 신선도를
알려준다. `next_rebalance_date` 는 엔진과 같은 규칙으로 계산하므로 실제 실행
시점과 일치한다.

주의: 사전 선택 전에는 `base.volatility` 가 null 이다. 그 구간에서는
`risk_comparison.base_volatility` 를 쓴다.

---

## 8. 알려진 항목 (미해결)

| 항목 | 영향 | 현재 대응 |
|---|---|---|
| 장중 가격 필터가 없다 | 장중 수집 시 잠정가가 종가로 굳는다 | 실행 시간대 준수(§2). 코드 가드는 시연 후 |
| `__FX__` 미저장 | 매 실행마다 11년치 환율 재다운로드 | 동작에는 문제없음. 야후 스로틀링 시 실패 지점 |
| `scheduled_for` 가 벽시계 기준 | 새벽에 깨어난 실행이 미국 종가 전에 그날을 선점할 수 있다 | 트리거가 07:10 이라 정상 경로는 안전 |
| `src/local/replay.py:34` 문법 오류 | 해당 모듈 import 불가 | 우리 작업과 무관. 팀에 공유 필요 |

---

## 9. 스크립트

| 파일 | 하는 일 | 쓰기 |
|---|---|---|
| `scripts/run_daily_task.bat` | 스케줄러가 부르는 일일 배치 | 있음 |
| `scripts/dev_ledger_report.py` | 참가자별 기록 + 독립성 점검 | 없음 |
| `scripts/dev_check_live_prices.py` | 가격 커버리지 + 야후 조회 가능 여부 | 없음 |
| `scripts/dev_seed_design_db.py` | 설계 DB 초기화(Node 없이) | 있음 |
| `scripts/dev_repair_intraday.py` | 장중 잠정가 제거 | `--apply` 시 |

`dev_` 접두사는 로컬 개발 전용이라는 뜻이다. `live` 프로파일에서는 거부되거나
쓰면 안 된다.

---

## 10. 아직 검증되지 않은 것 **[미검증]**

목요일(10-01) 이후 이 절을 채운다.

- **월간 리밸런싱 실제 실행.** 코드와 드라이런은 준비됐고 10-01 배치가 자동으로
  돌린다. 드라이런 기준으로는 밴드가 대부분의 주문을 막을 전망이다
  (2026-09-29 기준 편차 최대 0.03%p, 밴드는 목표의 ±10%).
- **분기 리밸런싱.** `frequency: quarterly` 로 바꾸면 3·6·9·12월 말에만 돈다.
  단위 테스트는 있으나 실제 분기 경계를 넘어본 적은 없다.
- **자동 실행 3일 연속.** 09-29 시작. 09-30 에 3일째가 된다.
- **배포 환경(Render + Neon).** 로컬 재시작 후 데이터 유지는 확인했다.
  PostgreSQL 이전(39,162행), 패리티 통과, 118일 쓰기 검증까지 끝났으나
  배포 환경에서 돌린 적이 없다.
- **GitHub Actions 크론.** `DATABASE_BACKEND` 누락을 고쳤지만 실행해본 적이
  없다. `workflow_dispatch` 로 `dry_run: true` 한 번 돌리면 검증된다.
