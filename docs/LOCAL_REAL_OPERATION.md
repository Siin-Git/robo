# 실제 날짜 기반 로컬 모의 운용

2026-10-03, `c587dae` 검토 커밋에서 분리한 `feat/local-forward-operation`.
기존 `integration/forward-pg`와 Draft PR #13의 범위는 바꾸지 않는다.
원격 DB, Render/Vercel, 백업 PR #12에는 변경하지 않았다.

## 현재 실행 환경

- 프론트: http://localhost:3073/setup/portfolio (API 프록시: 127.0.0.1:8073).
- 새 계정 `capstone01@example.com`으로 로그인한 설정 화면을 열었다. 사용자가
  위험 수준·인사이트를 선택하고 직접 확정한다. 에이전트가 대신 확정하지 않았다.
- 데이터: 저장소 루트의 `.local/real-forward/`. worktree 밖의 지속 디렉터리이며
  Git에서 제외했다. 인증은 `capstone_demo.db`, 운용/판단/원장은
  `portfolio_design.db`. 앞의 파일명은 기존 구현의 이름이며 합성 DB를 뜻하지 않는다.
- 계정 파일: 같은 디렉터리의 `accounts.json` / `accounts.md` (비밀번호는
  화면·로그·Git에 출력하지 않는다). 디렉터리는 0700, 계정 파일은 0600.
- 시계는 시스템 KST이며 API의 `now_utc`를 교체하지 않는다. 실가격은 기존
  Yahoo 공급자/환산 엔진을 사용한다. 증권사 주문을 전송하지 않는 모의 운용이다.
- 이전 합성 시연은 별도 `/private/tmp` DB와 127.0.0.1:3063/8063에서 보존했다.
  합성 환경은 `127.0.0.1`, 실제 운용은 `localhost`로 열어 쿠키를 분리한다.

`init`은 처음에 빈 두 DB를 Alembic head(0007)로 준비하고 새 계정과 테마
구성만 생성한다. 기존 계정·판단·가격·체결·성과를 복사하지 않는다.
기존 manifest가 있으면 계정/DB를 다시 만들지 않는다. 표식 없는 기존 DB나
합성 manifest를 실제 운용 데이터로 채택하지 않는다.
상속한 PostgreSQL URL과 합성 가격/계정 입력 환경값을 명시적으로 비워
API와 daily 모두 동일한 로컬 운용 DB를 사용한다.

## 시작·중지·실행

`.work/local-forward-operation`에서 다음을 실행한다. `init`은 최초 한 번만
필요하며 재실행해도 기존 표식이 있으면 보존한다.

```sh
.venv/bin/python scripts/local_operation.py init --data-dir ../../.local/real-forward
.venv/bin/python scripts/local_operation.py serve --data-dir ../../.local/real-forward
.venv/bin/python scripts/local_operation.py stop --data-dir ../../.local/real-forward
.venv/bin/python scripts/local_operation.py daily --data-dir ../../.local/real-forward
.venv/bin/python scripts/local_operation.py status --data-dir ../../.local/real-forward
.venv/bin/python scripts/operation_schedule.py status --data-dir ../../.local/real-forward
.venv/bin/python scripts/operation_schedule.py pause --data-dir ../../.local/real-forward
.venv/bin/python scripts/operation_schedule.py resume --data-dir ../../.local/real-forward
```

데이터 디렉터리의 `start-servers.command`, `stop-servers.command`,
`pause-batch.command`, `resume-batch.command`, `run-batch.command`,
`status.command`도 같은 명령을 호출한다. 서버 중지는 배치를 중지하지 않는다.
배치 중지는 웹/API를 중지하지 않는다. 재개 시 `RunAtLoad`로 한 번 시도한다.
웹/API 자동 시작은 등록하지 않았다. 재부팅 후에는 `start-servers.command`를
실행해야 화면에 접속할 수 있고, 예약 배치는 서버가 꺼져 있어도 DB에 기록한다.
다른 작업의 프로세스나 예약은 종료하지 않는다. 서버 런처는 포트 충돌 시
실행을 거절하고 자신이 시작한 프로세스 그룹만 정리한다.

로그: `logs/api.log`, `logs/web.log`, `logs/daily.log`,
`logs/scheduler.log`, `logs/scheduler-error.log`.
`last-run.json`은 마지막 시도, `portfolio_design.db.scheduled_jobs`는 작업 이력이다.
`SKIPPED`는 앞선 성공을 취소한 상태가 아니라 같은 날짜의 중복 실행 방지다.

## 자동 실행과 보호

등록한 사용자 LaunchAgent는 하나: `com.roboadvisor.local-forward.daily`.
파일은 `~/Library/LaunchAgents/com.roboadvisor.local-forward.daily.plist`.
매일 **07:30, 이 맥의 달력 시간대**로 실행한다. 등록 시 시스템 KST(+0900)를
확인했다. Python에도 `TZ=Asia/Seoul`을 지정하지만 맥의 시스템 시간대를
바꾸면 LaunchAgent 달력 시각도 달라지므로 다시 확인해야 한다.
2026-10-03 실행 이후 다음 달력 실행은 **10월 4일 07:30 KST**다.

기존 관련 LaunchAgent/LaunchDaemon/crontab/배치 프로세스가 없음을 확인한 뒤
등록했다. daily만 등록했고 월간/주간 재조정 작업을 추가로 예약하지 않았다.
실행 주체는 이 맥의 로그인 사용자다. 기존 엔진 분류상 `FORWARD_EXECUTOR=notebook`
을 사용한다. Actions나 팀원의 원격 배치에는 이 로컬 SQLite 경로가 제공되지 않는다.
worktree와 Python 환경을 유지해야 하며 경로를 이동하면 예약을 다시 준비해야 한다.

수동·예약 실행 사이에는 파일 잠금, 동일 DB의 `scheduled_jobs` 일자 슬롯이
함께 적용된다. 기존 거래시간 보호(KST 한국 평일 09:00–15:30,
미국 22:30–06:00)를 유지하며 `--force`는 제공/사용하지 않는다.
거래시간 보호로 거절되면 다음 안전한 실행을 기다린다. 자동 반복 재시도는 없다.
같은 날 이미 성공한 배치 뒤에 포트폴리오를 확정했다면 다음 날짜 배치가 처리한다.

잠든 맥은 예약 이벤트를 깨운 뒤 한 번으로 모아 실행한다. 꺼짐/로그아웃 상태에서는
이 사용자 에이전트가 동작하지 않고 다음 로그인/로드 때 `RunAtLoad`로 한 번
시도한다. 자동 전원 켜기·잠 깨우기 기능은 없다. 깨어난 시각이 거래시간이면
엔진 보호가 우선한다. 실제 잠자기/전원 끄기 실험은 하지 않았다.
근거: [Apple 예약 작업 문서](https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/ScheduledJobs.html).

누락 기간은 가격 공급자의 실제 과거 가격을 자산별 마지막 저장일 이후부터
수집한다. 대기 계획은 기존 엔진의 효력일 이후 첫 적격 종가로 모의체결하고,
평가는 실행 시점의 최신 투자자산 가격일에 기록한다. **꺼져 있던 모든 날짜의
NAV/성과를 소급 생성하는 기능은 없다.** 과거 가격 입력을 저장하는 것과
사용자 확정 이전 성과를 만드는 것은 다르다. 공급자 누락/지연은 로그·작업
통계의 실패/지연 항목으로 남고 임의 가격으로 보충하지 않는다.

## 직접 확인한 결과와 한계

| 구분 | 검증 결과 |
| --- | --- |
| 실제 예약 실행 | 10월 3일 14:54:28 KST 시작, 14:54:45 KST 성공 종료, launchd exit 0 |
| 실제 시장 데이터 | `live-refresh` 42,010행, 최신 투자자산 가격일 10월 2일, 실패·지연 목록 없음, SYNTHETIC 행 0 |
| 실제 사용자 원장 | 아직 판단 확정 0, 주문·체결·NAV 0. 사용자 직접 확정을 기다리는 정상 상태 |
| 같은 날 재실행 | 수동 실행과 예약 중지·재개 후 실행 모두 SKIPPED; 가격·주문·체결·NAV 건수 유지, 성공 작업은 1개 |
| 실제 서버 재시작 | 계정/가격/판단/주문/체결/NAV/보유 테이블의 건수·내용 해시 일치, 로그인 설정 화면 새로고침 성공 |
| 폐기 DB 파이프라인 | API 확정 → 효력일 이후 daily 체결 → 현금+보유평가액=NAV → API 조회, 같은 DB·중복 없음·재시작 후 판단/원장 유지 검증 |
| 백엔드 | Python 3.11, 폐기 PostgreSQL 포함 전체 475 passed; 최종 추가 FX/NAV·로컬 운용·대기 판단 회귀 15 passed |
| 프론트 | 59 passed(12 files), 프로덕션 빌드 및 타입 검사 통과 |

관측 없는 실제 DB에 과거 확정/합성 성과를 채우지 않았다. 모의체결·평가의
실제 실가격 경로는 사용자 확정과 효력일 이후 가격이 확보된 다음 실행에서
확인해야 한다. 위 폐기 DB 파이프라인은 통제한 가격/시계를 쓰는 회귀 테스트이며
실제 운용 체결 증거가 아니다.

10월 3일 토요일에 확정하면 기존 정책상 효력일은 10월 5일 월요일이다.
일요일 또는 월요일 07:30 실행에 아직 10월 2일 가격만 있으면 체결하지 않는다.
효력일 이후 적격 가격이 실제 공급될 때 처리하며 특정 미래 체결일을 보장하지 않는다.

기존 기능의 한계는 그대로다: KEEP/ADJUST는 구성 유지/재설계 선택이며 주문
승인·거절이 아니다. 예상↔실제 숫자 차이는 현재 모두 NOT_COMPARABLE이고,
기간이 지나도 자동 완성되지 않는다. 시장·안전자산 기준은 미합의다.
원격 배포, 실제 미래 예약 실행 및 실가격 체결, 물리적 잠자기/전원 복구는
이번 로컬 검증 완료로 주장하지 않는다.

코드 커밋은 `4b791c5`(FX 입력 보존/NAV 날짜),
`24ed042`(지속 로컬 환경/예약/격리 테스트)이며 원격에 푸시하지 않았다.
