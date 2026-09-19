# Render 데모 배포

기존 `render.yaml`은 일반 PostgreSQL 모드입니다. 이번 시연은 **`render.demo.yaml`**을 사용합니다.

## 생성할 리소스

- `robo-capstone-web`: Next.js public Web Service, Free, Singapore
- `robo-capstone-api`: FastAPI public Web Service, Free, Singapore, 단일 프로세스
- 영구 디스크와 유료 리소스는 생성하지 않습니다.
- DB: `/tmp/capstone-demo/capstone_demo.db` — PostgreSQL은 만들지 않음

두 서버는 모두 Free 플랜입니다. 15분 비활성 후 대기 상태가 되며 첫 요청 시 기동에 시간이 걸릴 수 있습니다. 재배포·재시작·대기 전환으로 임시 DB가 사라지면 13명과 고정 NAV를 다시 생성합니다. 세션과 변경한 비밀번호 등은 초기화됩니다. 무료 인스턴스 시간은 워크스페이스 전체에서 월 750시간을 공유하므로 두 서버를 계속 켜 두는 용도로는 적합하지 않습니다. 결제수단이 없다면 무료 한도 초과 시 서비스/빌드가 중지됩니다.
자동 배포는 꺼져 있습니다. 코드 변경 후 해당 서비스에서 Manual Deploy를 실행합니다.

## 최초 배포

1. Render에 로그인하고 **New → Blueprint**를 선택합니다.
2. GitHub에서 `MinchoLover/robo` fork 저장소 접근을 연결합니다. 권한을 선택할 수 있다면 이 저장소만 선택합니다.
3. Branch: `feat/capstone-demo-mvp` (main에 병합한 뒤라면 main)
4. Blueprint Path: `render.demo.yaml`
5. Blueprint 이름을 정하고 두 서비스 모두 Free이고 디스크가 없는지 확인한 뒤 생성합니다.
6. API 시작 시 seed가 자동 실행됩니다. 최초에는 13명을 만들고, 이후 실행은 기존 계정·NAV·비밀번호를 덮어쓰지 않습니다.
7. `robo-capstone-web` 화면의 실제 `https://…onrender.com` 주소를 엽니다.

API 주소는 Blueprint에서 백엔드의 `RENDER_EXTERNAL_HOSTNAME`을 참조해 자동 연결합니다. 무료 서버는 private network 수신을 지원하지 않으므로 Next.js 시작 명령이 공개 HTTPS URL을 구성합니다. 브라우저는 같은 웹사이트의 `/api/v1`만 호출하므로 별도의 브라우저용 API URL이나 CORS 도메인 입력이 필요하지 않습니다.

## 접속 검증

- capstone01 로그인 → Dashboard 테마·성과·차트 확인
- Ranking 13명 및 Return / Sharpe / MDD 정렬 → 02 상세 페이지 확인
- Logout → capstone03 로그인 → 새로고침 후 계정 유지 확인
- 응답 쿠키 `ra_session`: HttpOnly, Secure, SameSite=Lax
- API 인스턴스가 초기화된 뒤 고정 계정·NAV가 다시 생성되는지 확인합니다. 기존 로그인 세션은 초기화될 수 있으므로 재로그인합니다.

계정: `capstone01@example.com` ~ `capstone13@example.com`
초기 비밀번호: `Capstone-Demo-2026!`

이 초기 비밀번호는 저장소에 공개된 시연용 값입니다. 실제 개인정보·자산을 넣지 마세요. 팀원별 사용 구분이 필요하면 각자 Account 화면에서 비밀번호를 변경한 뒤 사용합니다. DB가 살아 있는 동안 seed 재실행은 비밀번호를 유지하지만, 무료 인스턴스가 초기화되면 초기 비밀번호로 돌아갑니다.

## 로그 / 장애 확인

- API 로그에서 `13 demo accounts ready`와 uvicorn 시작을 확인합니다.
- 웹에서 503 `UPSTREAM_UNAVAILABLE`이면 API가 Live인지 먼저 확인합니다.
- 비교 데이터가 없으면 API 설정의 `APP_PROFILE=local`, `CAPSTONE_DEMO=1`, `CAPSTONE_DATA_DIR=/tmp/capstone-demo`를 확인합니다.
- 웹이 일반 모드로 보이면 `NEXT_PUBLIC_CAPSTONE_DEMO=1`을 설정한 상태에서 다시 **빌드**합니다.
- `.env.local` 및 로컬 DB를 업로드하지 않습니다. 필요한 설정은 Blueprint에 들어 있습니다.
- 시연 5분 전에 웹사이트를 열어 로그인까지 확인하세요. 무료 플랜의 기동 지연을 고려합니다.

## 공유 문구

실제 배포 완료 후 `<웹 주소>`를 교체하여 팀원에게 전달합니다.

> 교수님 시연용 Robo Advisor: <웹 주소>/login
> 계정: capstoneXX@example.com (배정된 번호)
> 초기 비밀번호는 별도로 전달합니다.
> 로그인 → 내 성과 → 참여자 성과 비교 → 참가자 상세 순서로 확인해주세요.
> 표시되는 NAV와 성과는 시연용 가상 데이터입니다.

실제 팀원 이름·연락처·계정 배정 목록은 저장소에 기록하지 않습니다.
