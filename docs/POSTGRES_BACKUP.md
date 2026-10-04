# PostgreSQL 두 DB 백업과 격리 복원

## 범위와 완료 기준

PR #12의 인증(`DATABASE_URL`)·운용(`CAPSTONE_DESIGN_DATABASE_URL`) DB별
custom-format 덤프 구조를 유지한다. 매일 01:00 UTC(10:00 KST), artifact 보관
90일이다. DB 전환, 앱/Render 재설계, 그래프, 기존 생성 파일 정리는 하지 않는다.
**이 PostgreSQL 백업은 현재 맥의 로컬 SQLite 운용 데이터를 백업하지 않는다.**

완료 기준은 정상 데이터와 정상 빈 테이블의 실제 덤프·격리 복원,
잘못된 설정/스키마/연결과 복원 오류의 명확한 실패, 다른 DB의 성공 덤프 보존이다.
코드/폐기 DB 테스트 완료와 운영 덤프/운영 복구 확인은 별도 상태다.

## 검증 방식과 한계

- `users` / `accounts, orders, trades, holdings_daily, nav_daily`의 기대 컬럼과
  기본키를 검사한다. 행 수는 진단 정보이며 **0행은 정상**이다.
- `CONFIG_MISSING`, `CONFIG_INVALID`, `CONNECT_FAILED`, `REQUIRED_TABLE_MISSING`,
  `REQUIRED_COLUMNS_MISSING`, `REQUIRED_PRIMARY_KEY_MISSING`, `DUMP_FAILED`를 구분한다.
- 비밀을 제외한 입력 호스트/포트, 서버 주소/포트, 실제 DB 이름/OID, 서버 버전,
  허용되는 경우 cluster system identifier를 manifest에 남긴다.
- 동일 host/port/database, Neon direct/pooler 별칭, 조회된 backend 또는 cluster+DB
  식별자가 같으면 두 대상이 같은 DB인 것으로 거부한다. DNS/proxy/클론에 따라
  중복을 놓치거나 클론을 같은 대상으로 판정할 수 있다. system identifier 조회
  권한이 없어도 백업 자체를 거부하지 않는다.
- 양쪽 DB가 공통 스키마를 가질 수 있으므로 스키마나 DB 이름·행 수만으로
  인증/운용 역할이나 실제 앱 연결을 확정할 수 없다. 소유자가 아래 기대 식별값을
  현재 앱 설정과 대조해야 한다. 설정되지 않았으면 `expected_target_configured=false`다.
- 각 DB의 덤프는 PostgreSQL의 일관된 snapshot이다. 두 DB 사이의 동시에 고정된
  전역 snapshot은 아니다. manifest의 사전 조회 건수와 덤프 건수가 동시 쓰기로
  다를 수 있으므로 운영 복원에서 건수만을 완전성 증거로 쓰지 않는다.
- `pg_restore --list`는 형식과 필수 테이블 목차만 검사한다.
  `archive_check=TOC_ONLY_NOT_A_RESTORE`, `restore_verified=false`를 기록하며
  실제 복원 성공으로 표시하지 않는다. 실패/부분 `.partial` 파일은 업로드하지 않는다.
- auth/design matrix는 `fail-fast: false`이며 각각 업로드한다. 한쪽 실패는
  workflow 전체 실패로 남고, 다른 정상 덤프와 각 진단 manifest는 보존한다.
  수동 로컬 실행도 부분 성공이면 종료 코드 1이다. 출력 디렉터리 재사용은 거부한다.
- URL·비밀번호는 CLI 인수가 아니라 libpq 환경값으로만 전달한다. 원시 stderr와
  예외 메시지는 출력하지 않는다. 덤프는 민감한 실제 데이터이므로 artifact 접근
  권한을 제한하고 Git/채팅/공개 로그에 첨부하지 않는다.

## 설정과 버전 지원

Settings → Secrets and variables → Actions:

| 종류 | 이름 | 확인 방법 |
| --- | --- | --- |
| Secret | `DATABASE_URL` | 현재 앱 인증 연결과 일치하는 전체 PostgreSQL URL을 소유자가 설정 |
| Secret | `CAPSTONE_DESIGN_DATABASE_URL` | 현재 앱 운용 연결과 일치하는 별도 DB URL을 소유자가 설정 |
| Variable | `PG_BACKUP_CLIENT_MAJOR` | 14–18 중 선택, 미설정 기본 17; 가능한 서버와 같은 major 사용 |
| Variable | `BACKUP_AUTH_HOST`, `BACKUP_AUTH_DATABASE` | 승인한 인증 endpoint 호스트(포트/자격정보 제외)와 DB 이름 |
| Variable | `BACKUP_DESIGN_HOST`, `BACKUP_DESIGN_DATABASE` | 승인한 운용 endpoint 호스트와 DB 이름 |

기대 식별값은 선택 설정이며 설정하면 불일치 시 실패한다. 처음 main 활성화 전에는
소유자가 대상 역할을 확인하고 이 값들을 지정하는 것을 권장한다. URL 전체나 secret
값을 보고서에 복사하지 않는다. 지원하지 않는 URL 옵션은 조용히 무시하지 않고 거부한다.
`channel_binding`, `target_session_attrs`, `application_name` 등 지원 옵션은
[공식 libpq 환경 변수](https://www.postgresql.org/docs/18/libpq-envars.html)에
명시적으로 매핑해 보안·대상 선택 조건을 유지한다.

지원 정책: PostgreSQL 서버/도구 major 14–18. `psql`, `pg_dump`, `pg_restore`는
같은 major여야 한다. 덤프 도구는 원본 서버 이상, 복원 서버는 덤프 도구 이상이어야
한다. 복원 도구는 manifest에 기록된 덤프 도구 major와 맞춘다. 클라이언트 17은
서버 18을 덤프할 수 없으며, 17로 만든 덤프를 14 서버에 복원한다고 보장하지 않는다.
CI는 일치하는 14/17/18 조합을 실제 시험한다. 15/16 또는 교차 major 조합은 버전
규칙을 통과해도 별도 환경에서 extension/객체 호환성을 확인해야 한다.
[PostgreSQL pg_dump 버전 규칙](https://www.postgresql.org/docs/17/app-pgdump.html).

역할·tablespace 같은 cluster 전역 객체는 `pg_dump`에 포함되지 않는다.
격리 복원은 `--no-owner --no-acl`로 수행해 새 복원 소유자를 사용한다. 실제 복구에는
원래 역할/권한, extension 설치·버전, 보안 설정을 소유자가 별도로 준비·재검증해야 한다.

## 폐기 환경에서 재현

기존 서버 대신 **새 loopback 전용 PostgreSQL cluster**, `backup_test` 관리자와
`postgres` 관리 DB를 사용한다. URL은 로그에 출력하지 않고 환경에만 설정한다.

```sh
# BACKUP_TEST_ADMIN_URL: 새 폐기 cluster의 관리 연결, 포트 필수
# 원격 호스트나 다른 관리자/DB는 테스트가 거부한다.
BACKUP_REQUIRE_RESTORE_TESTS=1 python -m pytest tests/backup -q
```

운영 secret 없는 `backup-tests.yml`이 서비스 컨테이너로 같은 시험을 수행한다.
고유한 폐기 DB를 생성해 실제 production 백업 스크립트로 덤프하고, 별도의
`robo_restore_*` DB로 실제 `pg_restore`한다. 정상/빈 데이터, 컬럼·기본키·FK·CHECK·
UNIQUE·인덱스·시퀀스 값과 다음 ID·함수/트리거를 비교·실행한다. 설정/필수 테이블·
컬럼 누락, 접속 실패, 동일 대상, 기대 대상 불일치, 손상 덤프, 실제 SQL 권한 부족
복원 실패와 전체 rollback, 비어 있지 않은 목적지 보존도 검사한다.

## 연결 실패의 읽기 전용 비교

`backup.yml`을 PR #12 head ref에서 `diagnose_connection=true`로 수동 실행하면
같은 runner·설치 클라이언트·동일 secret으로 다음 두 방식을 비교한다. 이 입력은
`inspection_only`나 일반 백업보다 우선하며 덤프·운영 쓰기를 수행하지 않는다.

- 해당 `psql`이 사용하는 공유 libpq로 원래 URI를 직접 파싱·연결한다
  (`PQconninfoParse`, `PQconnectdbParams`의 expanded dbname).
- 현재 `Connection`의 URI→환경변수 변환을 거쳐 같은 `psql`로 연결한다.
- 양쪽에서 `BEGIN READ ONLY` 후 연결 식별/SSL/읽기 전용 상태만 SELECT하고
  연결을 닫아 rollback한다. URI/자격값은 argv·로그·artifact에 넣지 않는다.
  원문 오류·notice는 메모리에서 분류하거나 폐기한다. 출력은 파라미터 이름별
  일치 여부, 고정 오류 코드, 비밀 없는 버전/상태와 DB 식별 fingerprint뿐이다.
- `BACKUP_*` 승인 변수는 **이 연결 진단에 적용하지 않는다**. 연결 성공이나
  두 방식의 일치는 실제 앱의 인증/운용 역할과 일치한다는 증거가 아니다.
  승인값은 앱의 실제 연결을 별도로 확인한 뒤에만 지정한다.

로컬에서도 secret은 환경에만 설정하고 아래처럼 실행할 수 있다.

```sh
python -m scripts.postgres_backup_diagnose --target design --output-dir /restricted/new-diagnostic
```

보안/대상 옵션을 제거해 연결을 시도하지 않는다. 고정 오류 코드는 URI 인코딩,
TLS 모드, channel binding 값/요구, 대상 session 값/불일치, 인증, DNS, 거부,
timeout, 존재하지 않는 DB 등을 구분하며 미분류는 `CONNECT_FAILED`로 남는다.

### 같은 secret 비교 결과 (2026-10-03)

[상세 비교 실행](https://github.com/Siin-Git/robo/actions/runs/37119843115)의 양쪽 job은
동일 secret, `psql/pg_dump/pg_restore` 18, 실제 공유 libpq 180006을 사용했다.
secret 갱신 시각은 이전 성공·실패 실행과 동일하다. 인증은 원래 URI/현재 변환의
모든 지정 파라미터가 일치하고 같은 DB로 읽기 전용 연결에 성공했다.
`sslmode=require`, `channel_binding=require`가 유효하며 native client TLS도 확인했다.
`pg_stat_ssl`의 backend SSL은 proxy 이후 구간이므로 client TLS와 혼동하지 않는다.

운용은 원래 URI의 **query에 여분 `=`**가 있어 native 파싱/연결이
`CONNECT_URI_EXTRA_EQUALS`로 실패했다. URI에는 제어 문자도 있다. 기존 변환은
`urlsplit`이 일부 제어 문자를 제거하고 HTML form 방식 query 파서를 사용해
malformed URI를 통과시켰으며, 변환된 `channel_binding`은 인정되는 값이 아니고
여분 assignment separator를 포함해 `CONNECT_CHANNEL_BINDING_INVALID`였다.
값 자체나 원문 오류를 공개하지 않았으므로 붙은 내용의 출처는 단정하지 않는다.

성공 커밋 `5f9e102`은 `PGCHANNEL_BINDING`이라는 잘못된 이름을 사용해 옵션을
무시했다. `623bb4d`가 공식 이름 `PGCHANNELBINDING`으로 바꾼 뒤 실패한 것은
유효하지 않은 원래 값이 실제 적용됐기 때문이다. 인증 비밀번호/TLS/network 문제로
단정할 근거가 없으며, 보안 옵션을 다시 무시해 성공시키지 않는다.

최소 코드 수정은 raw 제어 문자와 잘못된 query separator/percent encoding을
고정 설정 오류로 거부하고 URI의 literal `+`를 공백으로 바꾸지 않는 것이다.
encoded `+`, `%`, 공백, `options`의 `=`는 한 번만 percent-decode한다.
secret은 변경하지 않았다. `BACKUP_*` 승인 변수도 설정하지 않았다.

소유자는 Actions의 **`CAPSTONE_DESIGN_DATABASE_URL`만** 실제 앱의 운용 연결과
비공개 대조하여 **한 개의 PostgreSQL URI**가 저장됐는지 확인한다. raw 제어 문자,
URI 외에 붙은 내용과 query의 여분 `=`를 제거해야 하며 원래 host/DB/user/password와
보안 정책은 유지한다. `channel_binding=require`라면 값은 정확히 `require`여야
하며 `sslmode=require`도 유지한다. option 값 안의 필요한 예약 문자는 URI 규칙대로
percent-encode한다. secret 값이나 잘못 붙은 내용을 채팅/공개 로그로 보내지 않는다.
수정 후 `diagnose_connection=true`를 다시 실행해 양쪽 연결/파라미터 일치를 확인한다.
그 다음에만 별도 앱 연결 확인을 통해 `BACKUP_*` 승인값을 지정한다.
main 병합·첫 운영 백업·운영 복원은 계속 보류한다.

## 실제 운영 덤프의 격리 복원 절차

1. 성공한 auth/design artifact와 **같은 실행의** JSON manifest를 제한된 장소에
   내려받는다. checksum, `BACKED_UP`, 서버/클라이언트 major, 필수 목차를 확인한다.
2. 운영 DB와 분리된 폐기 환경에 비어 있는 `robo_restore_*` DB 두 개를 소유자가
   만든다. 이름은 안전성 증명이 아니다. endpoint/프로젝트와 접근 범위를 확인하고
   복원 계정에는 **운영 DB 쓰기 권한을 부여하지 않는다**. 필요한 extension을 준비한다.
3. `BACKUP_RESTORE_DATABASE_URL`을 해당 폐기 DB로 설정한다(전체 URL 출력 금지).
   백업용 두 URL이 접근 가능하다면 환경에 유지해 목적지 중복 검사도 수행한다.

```sh
python scripts/postgres_backup.py restore \
  --dump /restricted/download/robo_auth.dump \
  --manifest /restricted/download/robo_auth.json --acknowledge-isolated
# design 파일 쌍과 별도 폐기 목적지로 반복
```

스크립트는 checksum/버전/원본과 동일 DB 여부/기존 테이블 등을 확인한다.
`--clean`, `--create`로 덮어쓰지 않는다. 실제 복원은 `--exit-on-error
--single-transaction --no-owner --no-acl`이며 SQL 오류는 실패·rollback이다.
[PostgreSQL pg_restore 설명](https://www.postgresql.org/docs/17/app-pgrestore.html).
4. `RESTORED`와 스키마 확인만으로 앱 복구를 선언하지 않는다. 주요 사용자/원장,
   FK·고유 제약·불변 트리거·시퀀스, 현금+보유평가액=NAV, 사용자 격리, 승인한
   snapshot 시점과 참조 버전/연결을 확인하고 결과를 기록한다.
5. 운영 DB에 복원하지 않는다. 폐기 환경 정리는 소유자 정책에 따른다.
   매일 운영 백업에 이 전체 복원 시험을 강제로 추가하지 않는다.

## 반영 순서

PR #12 head에는 수정만 추가한다. develop 전체를 main 대상 PR에 합치지 않는다.
동일 수정 커밋을 최신 develop의 별도 브랜치에 적용하고 기존 CI와 복원 CI가
통과한 커밋을 develop PR로 병합한다. 예약은 **기본 브랜치 main** workflow에서
실행하므로 develop 병합만으로 운영 백업이 고쳐졌다고 보고하지 않는다.

main 반영은 CI 통과, 실제 Actions 두 대상/권한 확인, main 앱 배포 영향 확인 후
백업 관련 변경만 수행한다. 연결 식별 조회는 `backup.yml`을 수정 브랜치 ref에서
`inspection_only=true`로 수동 실행할 수 있고 덤프를 생성하지 않는다. main 활성화
후 `inspection_only=false`로 첫 백업을 실행해 양쪽 artifact와 workflow 결과를
확인한다. 운영 덤프의 실제 격리 복원은 별도 접근이 확보된 경우에만 완료로 기록한다.

## 로컬 검증 기록 (2026-10-03)

- PostgreSQL 14.19의 새 `/private/tmp/robo-backup-test.*` cluster에서 복원 회귀
  **12 passed**. 정상 데이터와 정상 빈 테이블 각각 auth/design 실제 복원 4회,
  checksum 손상 감지와 실제 손상 archive/권한 오류 복원 실패를 확인했다.
- PR #12 기존 CI와 같은 백엔드 명령: **87 passed + 37 passed**
  (기존 선택 조건에 따른 deselected 5+2). 운영 DB는 사용하지 않았다.
- PR #12 프론트 **50 passed(9 files)**, 별도 출력 디렉터리의 프로덕션 빌드 통과.
- 최신 develop 기반 전체 백엔드 **489 passed**(폐기 PostgreSQL 포함), 프론트
  **59 passed**, build 통과. PR #12보다 많은 기존 기능을 포함한 develop에서도 검증했다.
- [PR #12 복원 CI](https://github.com/Siin-Git/robo/actions/runs/37107421267):
  PostgreSQL **14/17/18 각각 12 passed**. PR #12 기존 backend/frontend push·PR CI도 통과.
- [첫 실제 Actions inspection](https://github.com/Siin-Git/robo/actions/runs/37107499779)은
  연결된 두 서버가 18인데 client 17이어서 의도대로 `SERVER_VERSION_INCOMPATIBLE`.
  이 요청에서 백업 전용 비밀 아닌 variable `PG_BACKUP_CLIENT_MAJOR=18`을 설정했다.
- [18로 재검사](https://github.com/Siin-Git/robo/actions/runs/37107828751)는 auth/design
  모두 `INSPECTED_ONLY`. 서로 다른 DB OID, 같은 cluster, 기대 컬럼/PK·조회 접근을
  확인했다. 덤프는 생성하지 않았고 `restore_verified=false`다.
- 이후 URL의 libpq 보안·대상 옵션 전달을 바로잡은 당시 코드의
  [연결 재검사](https://github.com/Siin-Git/robo/actions/runs/37109498633)는 인증 DB
  `INSPECTED_ONLY`, 운용 DB `CONNECT_FAILED`로 부분 실패했다. 반복 검사에서도
  동일 결과이며, 인증 검사도 상대 DB 식별을 확인하지 못했다. 앞선 양쪽 성공을
  운영 준비 완료로 취급하지 않는다. 비밀이 포함될 수 있는 원문 오류는
  출력하지 않아 그때는 세부 원인을 확인하지 못했다. 이후 위의 같은 secret 비교로
  malformed query·제어 문자와 기존 코드의 옵션 무시/URI 변형을 확인했다.
  보안 옵션은 유지하며 소유자의 조치는 위 `CAPSTONE_DESIGN_DATABASE_URL` 항목을 따른다.
- 진단/URI 수정 후 폐기 PostgreSQL 로컬 회귀 **35 passed**. 읽기 전용 동일 DB 비교,
  비밀 없는 오류/옵션 형태, literal/encoded `+`·`%`·공백·`options`의 `=`,
  제어 문자와 잘못된 query 거부를 기존 실제 복원 시험과 함께 검증했다.
- 현재 `BACKUP_AUTH_HOST/DATABASE`, `BACKUP_DESIGN_HOST/DATABASE`는 미설정.
  관측한 이름·호스트를 자동으로 승인 기준에 복사하지 않았다. 실제 앱의 인증/운용
  연결과 일치하는지는 소유자의 독립 확인이 필요하다.
- main 자동 배포 연결도 확인되지 않았다(현재 GitHub 계정으로 webhook/배포 연결
  관리 정보를 조회할 수 없음). 따라서 조건부 main 병합과 첫 운영 백업은 보류한다.
  main에는 아직 기존 주간 단일 DB/14일 보관 workflow가 남아 있다.
- 폐기 DB 성공은 운영 덤프 복원 증거가 아니다. 운영 덤프의 격리 복원은 미검증이며
  이 기록은 운영 DB 변경이나 실제 앱 배포 완료를 의미하지 않는다.
