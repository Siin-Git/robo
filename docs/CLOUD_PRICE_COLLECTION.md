# 운영 가격 수집 복구 — 2026-10-05

## 범위와 장애

운영 기본 브랜치 `release/public-operation`의 `b6add639`에서 분리한 수정이다.
`daily-forward`의 07:30 KST 예약이 10:09 KST에 시작한 실행 `37250327467`은
한국 장중 guard에서 exit 2로 끝나 가격 수집까지 도달하지 못했다. 이 수정은
스케줄 지연 여부와 관계없이 종료된 세션만 수집하는 전용 CLI를 추가한다.

**자동 거래 운용은 아직 시작하지 않는다.** 실제 운영 조회에서 확인된 첫 결정
효력일은 2026-10-05이며 거래·보유·NAV가 아직 없는 상태다. 가격 수집 복구는
참가자 READY, 공동 T0, 주문 집행 승인이나 공동 시작 엔진의 구현을 의미하지 않는다.

기존 2015~2026-10-02 가격, 결정, 주문, 체결, 보유, NAV, 상태, job, event를
수정하지 않는다. 3073/3099 시연과 3103 실제 관측용 로컬 자동화도 대상이 아니다.
백업 PR #12 workflow, 웹 화면, Render/Vercel 설정, DB schema는 변경하지 않는다.

## 수집 계약

- `python -m src.forward.run_prices --start 2026-10-05`만 운영 자동 수집에서 실행한다.
  기존 `run_daily`의 거래 경로와 `--force`를 호출하지 않는다.
- 실제 조회 하한은 명시 시작일과 최초 결정 효력일 중 늦은 날이다. `--scheduled-for`는
  실행 설명용 날짜다. 종료 여부는 실제 현재 시각으로 판단한다.
- Yahoo IANA 거래소 시간대로 일봉 날짜를 해석한다. London BST 자정과 미국 DST를
  반영하며 고정 UTC offset이나 모든 자산의 날짜를 일괄 이동하는 방법을 쓰지 않는다.
- 당일 주식/ETF는 공급자의 정규 세션 종료 후 30분이 지나야 포함한다. 종료 정보가
  없으면 당일 값은 보류한다. FX는 London 세션 날짜가 지나야 포함하며, 자정 너머까지
  진행 중인 세션이라는 공급자 정보가 있으면 추가 보류한다.
- 공급자가 실제 반환한 평일 가격만 저장한다. 휴장일 값을 채우지 않는다. USD 비헤지
  자산과 테마는 같은 세션 날짜의 확정 FX 관측값을 곱한다. 기존 레거시 FX를 대신
  사용하지 않는다. 정확한 날짜 FX가 없으면 해당 자산의 해당 날짜는 보류한다.
- 매번 하한 이후를 다시 읽어 늦게 온 과거 누락 가격도 회수한다. 이미 존재하는
  `(asset_id, date)`는 값/출처에 관계없이 보존한다. DB의 `ON CONFLICT DO NOTHING`이
  중복 삽입과 덮어쓰기를 추가로 막는다. 신규 출처는 `yahoo-closed-session-v1`이다.
- 정상 빈 응답, 휴장, 진행 중 세션과 실제 연결/파싱 오류를 구분한다. 정상 빈 자료는
  0건 성공이 가능하다. 실제 오류는 자산별 오류 유형을 보고하고 CLI exit 1이다.
  유효한 다른 자산은 저장할 수 있으며 `PARTIAL_FAILURE`로 표시한다.
- 한 번의 가격 저장은 한 트랜잭션이다. SQL 중간 실패는 전체 가격 배치를 롤백한다.
  SQL advisory transaction lock은 다른 가격 수집 프로세스의 동시 실행을 거부한다.

기존 가격은 수정하지 않으므로 레거시 이력의 날짜/정렬 문제를 교정하는 작업은 포함하지
않는다. 늦게 추가된 가격을 근거로 과거 의사결정이나 체결을 재생하는 기능도 없다.

## 실행과 읽기 전용 검증

CLI는 `DATABASE_BACKEND=postgres` 및 명시적인 `CAPSTONE_DESIGN_DATABASE_URL`이
필요하다. `DATABASE_URL`의 인증 DB나 SQLite로 대체하지 않는다. 기존 DB 연결 초기화,
마이그레이션, job/event 기록 코드를 호출하지 않는다. 쓰기 SQL은 가격 INSERT뿐이다.

```sh
python -m src.forward.run_prices --start 2026-10-05 \
  --expected-database robo_design --expected-revision 0008 --dry-run \
  --output /private/tmp/closed-price-preflight.json

python -m src.forward.run_prices --start 2026-10-05 \
  --expected-database robo_design --expected-revision 0008 \
  --output /private/tmp/closed-price-report.json
```

위 명령의 환경은 승인된 실행 환경에서 설정하며 URL/비밀번호를 출력하지 않는다.
보고서는 DB 이름, 스키마 revision, `SHA256(host + '/' + database)[:16]` 식별자,
조회 하한, 자산, 보류·실패와 추가 행 수를 기록한다. 연결 예외 문자열은 secret 노출
가능성이 있어 기록하지 않는다. 대상 DB/스키마가 다르면 수집 전에 실패한다.

`--dry-run`은 연결 시작 옵션 `default_transaction_read_only=on`으로 DB 서버가
읽기 전용을 강제한다. 거래소 조회나 가격 저장을 호출하지 않으며 DML뿐 아니라 DDL도
거부된다. 이 모드는 기존 daily/weekly/monthly의 dry-run과 별개의 구현이다.

## GitHub Actions 적용 범위

현재 저장소 기본 브랜치가 `release/public-operation`이므로 이 브랜치에 수정이
반영되어야 예약 실행도 변경된다. checkout에는 별도 ref override가 없으며 수동
dispatch는 선택한 ref의 코드를 실행한다. 기능 브랜치 검증이 예약 실행 교체를 뜻하지 않는다.

`daily_forward.yml`의 이름은 유지하면서 실행 대상을 `run_prices`로 바꾼다.
기존 07:30 KST 예약에 09:17/17:17 KST 재시도를 추가한다. 지연 실행의 안전성은
cron 시각이 아니라 세션 완료 필터가 담당한다. `forward-jobs` 직렬 실행 그룹은 유지한다.
실행 보고서는 7일 보관 artifact로 저장한다. 실제 원격 0건 성공은 신규 삽입의 운영 실증과
구별해서 보고해야 한다. 새 가격이 생긴 실행의 전후 DB 비교까지 확인해야 한다.

주간/월간은 `FORWARD_EXECUTOR=actions`와 **별도** `FORWARD_TRADING_ENABLED=true`를
모두 요구한다. 입력 dry-run도 이 가드를 우회하지 않는다. 이 플래그를 켜기 전에 공동
T0 엔진 통합·준비 상태 검증·사용자 승인이 별도로 필요하다. 플래그 자체가 공동 시작을
보장하지 않으며, 이번 복구에서는 켜지 않는다. daily workflow는 플래그와 관계없이
가격만 수집한다. 전체 거래 운용의 스케줄 재연결은 후속 작업이다.

## 검증

Python 3.11.15의 수집·provider·workflow 계약 집중 검사 **45 passed**. 이 중
6개는 폐기 PostgreSQL 14 로컬 DB `cloud_price_test`에서 실제 SQL로 확인했다.

전체 백엔드 실행은 **598 passed / 22 skipped**였다. skip은 PostgreSQL 환경이 필요한
검사이며 이 중 이번 수집기 PG 6개는 위 별도 실행으로 통과했다. 이후 추가한 provider
응답 분류/중복 관측 3개도 위 집중 검사에 포함해 통과했다. 나머지 기존 PG 검사는
기존 CI의 독립 DB 환경에서 검증된다. 프론트는 변경하지 않아 재검사하지 않았다.

- 지연된 한국 장중, 정규 마감 30분 경계, 미국 DST 양 계절, FX London 자정,
  Yahoo 원본 응답의 봄/가을 DST 날짜 해석, 정확한 날짜 FX, 휴장 무채움.
- 당일 반복 0추가, 최신일보다 앞선 누락 가격의 지연 도착, 기존 가격 불변,
  정상 빈 응답, 실제 오류의 exit 1, 독립 자산의 부분 성공, 잘못된 가격 거부.
- 실제 PostgreSQL 시작부터 읽기 전용 적용, INSERT/CREATE 거부, 실제 preflight
  전체 표 불변, 다른 DB/스키마 거부, 가격 외 11개 표 동일, 가격 배치 롤백,
  writer 동시 실행 거부, 기존 가격/같은 날 재시도 보존.

원격 Yahoo를 테스트에 호출하지 않는다. 캡처한 공개 응답과 제어된 값으로 검증한다.
PG 테스트는 `PRICE_TEST_DATABASE_URL`에 loopback 호스트와 정확한 DB 이름
`cloud_price_test`가 있어야 실행된다. 운영 DB 환경변수를 테스트 주소로 쓰지 않는다.
CI는 기존 폐기 PostgreSQL 서비스에 독립 `cloud_price_test` DB를 만들어 이 검사를 실행한다.

```sh
PRICE_TEST_DATABASE_URL=postgresql://price_test@127.0.0.1:55489/cloud_price_test \
  python -m pytest -q tests/forward/test_price_only.py tests/forward/test_price_only_pg.py \
  tests/forward/test_closed_sessions.py tests/test_yahoo_session_dates.py \
  tests/forward/test_executor_contract.py
```

개발 담당은 로컬 구현/검증/커밋까지만 수행한다. 운영 백업, 승인된 원격 읽기 전용
preflight, PR/CI/반영, 실제 실행과 재시도, 운영 전후 보존 확인은 배포 담당이 별도로 수행한다.
