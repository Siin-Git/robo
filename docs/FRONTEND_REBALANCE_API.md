# 프론트 연결용 — 리밸런싱 결과 API

요청하신 두 가지에 대한 답입니다.

**요약부터 드리면**, 2번(사용자별 분리)은 확인 완료이고, 1번은 **네 항목 중
둘이 현재 API 에 없습니다.** `/me/ledger/status` 와 `/me/alerts` 만으로는
연결이 안 됩니다. 아래에 지금 되는 것과 안 되는 것을 나누고, 빠진 부분을 채울
엔드포인트 안을 제안드립니다.

---

## 1. 지금 내려오는 것

### `GET /api/v1/me/portfolio` — 목표 비중

```json
{
  "participant_id": "P001",
  "as_of": "2026-09-28",
  "benchmark_version": "CORE_V0.3",
  "expected_return": 0.05909095770037283,
  "expected_return_basis": "black_litterman_v0; themes inherit the funding equity average (no independent theme view)",
  "expected_volatility": 0.0812,
  "tracking_error": 0.0,
  "risk_comparison": {
    "base_volatility": 0.0812,
    "personalized_volatility": 0.0812,
    "as_of": "2026-09-28",
    "method": "5Y weekly Ledoit-Wolf"
  },
  "weights": [
    { "asset_id": "us_equity",   "weight": 0.2663, "asset_type": "core",  "ticker": null },
    { "asset_id": "us_treasury", "weight": 0.2407, "asset_type": "core",  "ticker": null },
    { "asset_id": "ai",          "weight": 0.075,  "asset_type": "theme", "ticker": "AIQ" },
    { "asset_id": "cash",        "weight": 0.0,    "asset_type": "cash",  "ticker": null }
  ]
}
```

`weights` 는 **목표 비중**입니다(`portfolio_targets` 의 최신 행). 실제 보유
비중이 아닙니다.

`asset_type` 이 `theme` 이면 `asset_id` 는 테마 id(`ai`), 그 외에는 코어 자산
id 입니다. 내부 저장은 `theme:ai` 형태이고 API 에서 접두사를 떼서 내려갑니다.

주의: 사전 선택 전에는 `risk_comparison.base_volatility` 가 null 일 수 있습니다.

### `GET /api/v1/me/ledger/status` — 기록 상태

```json
{
  "has_history": true,
  "first_valuation_date": "2026-09-28",
  "last_valuation_date": "2026-09-29",
  "observation_count": 2,
  "last_updated_at": "2026-09-29T23:04:11.238412+00:00",
  "latest_price_date": "2026-09-29",
  "data_freshness": "OK",
  "next_rebalance_date": "2026-10-01",
  "stale_price_days": 14
}
```

`data_freshness` 는 `OK` / `STALE` / `NO_DATA` 입니다. `next_rebalance_date` 는
엔진과 같은 규칙으로 계산하므로 실제 실행 시점과 일치합니다.

### `GET /api/v1/me/alerts` — 이벤트 기반 알림

```json
{
  "items": [
    {
      "alert_id": "E000312",
      "type": "TRADE_EXECUTED",
      "date": "2026-09-28",
      "occurred_at": "2026-09-29T23:03:58.117204+00:00",
      "title": "주문이 체결되었습니다",
      "detail": { "trade_id": "T0042", "order_id": "O0042", "asset": "us_equity",
                  "execution_at": "2026-09-28", "price": 519282.28,
                  "quantity": 51.3, "cost": 13320.5 },
      "severity": "info"
    }
  ],
  "total": 234,
  "limit": 50,
  "offset": 0
}
```

나오는 `type` 목록입니다.

| type | severity | 언제 |
|---|---|---|
| `INITIAL_ORDER` | info | 최초 편입 주문 생성 |
| `ORDER_CREATED` | info | 리밸런싱 주문 생성 |
| `TRADE_EXECUTED` | info | 체결 |
| `REBALANCE_EXECUTED` | info | 주간 액티브 리밸런싱 실행 |
| `CASH_SCALED` | warning | 현금 부족으로 매수 축소 |
| `VIEW_SUBMITTED` / `VIEW_REJECTED` | info / warning | 주간 의견 |
| `BASE_SELECTED` / `ONBOARDING_COMPLETED` | info | 온보딩 |
| `RISK_REFRESHED` | info | 위험 모형 갱신 |
| `PRICE_STALE` | warning | 가격 지연(이벤트 아님, 상태에서 합성) |
| `PRICE_REFRESH_FAILED` | warning | 가격 수집 실패. **전 사용자 공통** |

`detail` 은 이벤트 페이로드 그대로라 타입마다 키가 다릅니다. 화면에서 쓰실
키가 정해지면 스키마를 고정해 드리겠습니다.

### 그 외 이미 있는 것

| 용도 | 엔드포인트 |
|---|---|
| NAV 추이 | `GET /me/performance/nav` |
| 기간별 성과 + 테마 기여도 | `GET /me/performance/dashboard?period=ALL` |
| 기본 대비 개인화 비교 | `GET /me/portfolio/summary` |
| 코어 대비 개인화 | `GET /me/portfolio/comparison` |

---

## 2. 지금 **없는** 것

| 요청하신 항목 | 상태 |
|---|---|
| 목표 비중 | `/me/portfolio` 의 `weights` |
| **현재(실제 보유) 비중** | **없음** |
| **자산별 매수/매도 필요 여부** | **없음** |
| 생성된 주문 | 알림으로 간접 확인만 가능 (`ORDER_CREATED`) |
| 최근 리밸런싱 기록 | 알림으로 간접 확인만 가능 |

**현재 보유 비중**은 `holdings_daily` 에 계좌·날짜·자산 단위로 쌓이고 있지만
API 로 나가는 경로가 없습니다. `performance/dashboard` 가 내부적으로 읽지만
테마 기여도만 반환합니다.

**자산별 매수/매도 필요 여부**는 엔진이 `execution.plan_orders` 로 계산합니다.
자산마다 `order`(주문) / `band`(밴드 안이라 건너뜀) / `unchanged`(변화 없음)
중 하나를 판정합니다. 이 판정이 API 로 나가지 않습니다.

**주문 목록**은 `orders` 테이블에 있지만 조회 엔드포인트가 없습니다. 알림의
`ORDER_CREATED` 에 `asset` 과 `target_weight` 가 들어 있어 부분적으로는
읽히지만, 주문 상태(`pending`/`executed`/`cancelled`)나 효력일별 묶음은
나오지 않습니다.

---

## 3. 제안 — 엔드포인트 두 개

요청하신 네 항목이 한 번에 해결됩니다.

### `GET /api/v1/me/rebalance` — 현재/목표/판정

엔진의 `plan_orders` 를 그대로 호출합니다. **드라이런과 같은 함수**라 화면에
보이는 판정과 실제 실행이 어긋나지 않습니다.

```json
{
  "as_of": "2026-09-29",
  "effective_date": "2026-10-01",
  "frequency": "monthly",
  "band": { "type": "relative", "threshold": 0.10, "min_absolute": 0.0 },
  "needs_rebalance": false,
  "summary": { "order": 0, "band": 8, "unchanged": 1 },
  "legs": [
    {
      "asset_id": "us_equity",
      "asset_type": "core",
      "ticker": null,
      "current_weight": 0.26663,
      "target_weight": 0.26630,
      "drift": -0.00033,
      "side": "sell",
      "action": "band"
    },
    {
      "asset_id": "ai",
      "asset_type": "theme",
      "ticker": "AIQ",
      "current_weight": 0.0,
      "target_weight": 0.075,
      "drift": 0.075,
      "side": "buy",
      "action": "order"
    }
  ]
}
```

| 필드 | 뜻 |
|---|---|
| `needs_rebalance` | `action == "order"` 인 자산이 하나라도 있으면 true |
| `action` | `order` 조정한다 / `band` 밴드 안이라 건너뛴다 / `unchanged` 변화 없음 |
| `side` | `buy` / `sell`. `action` 과 무관하게 방향만 표시 |
| `drift` | `target - current`. 양수면 더 사야 함 |
| `effective_date` | 다음 리밸런싱 주문의 효력일 |

화면에서 "조정 필요"를 판단하실 때 `drift` 크기로 직접 계산하지 마시고
`action` 을 쓰시면 됩니다. 밴드 규칙이 바뀌어도 프론트를 안 고쳐도 됩니다.

### `GET /api/v1/me/orders?limit=50&offset=0&status=pending`

```json
{
  "items": [
    {
      "order_id": "O0042",
      "asset_id": "us_equity",
      "asset_type": "core",
      "ticker": null,
      "side": "buy",
      "target_weight": 0.2663,
      "submitted_at": "2026-09-28T00:00:00+00:00",
      "effective_at": "2026-09-28",
      "status": "executed",
      "executed_at": "2026-09-28",
      "execution_price": 519282.28,
      "quantity": 51.3
    }
  ],
  "total": 8,
  "limit": 50,
  "offset": 0
}
```

`effective_at` 으로 묶으면 리밸런싱 회차별 기록이 됩니다. `status` 로 필터해
대기 주문만 볼 수도 있습니다.

### 작업량

두 개 합쳐 **반나절** 정도로 봅니다. 새 테이블은 필요 없고 기존 데이터를
읽기만 합니다. 계약 테스트도 같이 넣겠습니다.

**필요하신지, 필요하시면 어느 쪽이 먼저인지 알려주시면 그에 맞춰 진행하겠습니다.**
`/me/rebalance` 하나만으로도 1번 요청의 대부분이 해결됩니다.

---

## 4. 사용자별 분리 — 확인 완료

**CAPSTONE 모드에서도 사용자별로 분리되어 저장되고 조회됩니다.**

### 저장

forward 엔진이 `portfolio_design.db`(대시보드가 읽는 설계 DB)에 기록하고,
13명 비교 시연 데이터는 `capstone_demo.db` 에 그대로 있습니다. 서로 덮어쓰지
않습니다.

모든 원장 테이블이 `account_id` 를 키로 갖고, 계좌는 참가자당 2개
(core + personal)입니다.

### 실제 데이터

09-28 에 13명 전원 최초 편입을 실행한 결과입니다.

```
participant  acc   ord   trd  hold  nav   last nav
P001           2    16    16    32    4  2026-09-29
...
P013           2    16    16    32    4  2026-09-29
------------------------------------------------
합계          26   208   208   416   52
```

계좌 26개에 주문 208건이 **계좌당 8건씩** 분리되어 쌓였고, 어느 참가자에도
연결되지 않은 기록은 0건입니다.

### 조회

`/me/*` 엔드포인트는 모두 로그인한 사용자의 `participant_id` 로만 조회합니다.
`/me/ledger/status` 와 `/me/alerts` 도 동일합니다.

예외가 하나 있습니다. `PRICE_REFRESH_FAILED` 는 운용 전체에 해당하는
사건이라 **모든 사용자에게 같이 보입니다.** 가격 수집이 멈추면 모두의 문제라
의도한 동작입니다.

### 검증

테스트로 고정해 뒀습니다(총 297개 통과).

- 참가자 13명을 서로 다른 목표 비중으로 실행 → 주문·체결·보유·NAV 가 계좌별로
  분리되는지
- 한 참가자를 실행해도 다른 참가자의 NAV 와 현금이 변하지 않는지
- 배치를 두 번 돌려도 행이 중복되지 않는지
- 두 사용자가 각각 로그인했을 때 `/me/ledger/status` 와 `/me/alerts` 의 결과가
  섞이지 않는지

`scripts/dev_ledger_report.py` 로 언제든 현재 상태와 독립성 점검을 보실 수
있습니다.

---

## 5. 참고 — 알아두시면 좋은 동작

**평가 기준일은 실행일이 아니라 마지막으로 종가가 확정된 날입니다.**
`last_valuation_date` 가 오늘이 아니어도 정상입니다. 미국 종가는 한국시간
다음날 새벽에 들어옵니다.

**주문과 체결 사이에 하루가 있습니다.** 주문은 효력일 이후 첫 거래일 종가에만
체결됩니다. 리밸런싱을 실행한 날 화면에는 `pending` 주문만 보이고 체결은
다음 날 반영됩니다.

**첫 NAV 행의 `daily_return` 은 null 입니다.** 전날이 없어 수익률을 계산할 수
없습니다. `cumulative_return` 은 0 입니다.

**밴드가 작동하면 주문이 0건일 수 있습니다.** 09-29 기준 드라이런에서 편차가
최대 0.03%p 라 208건이 모두 밴드에 막혔습니다. 목표 대비 ±10% 안에서는 거래
비용만 나가므로 조정하지 않는 것이 정상 동작입니다. 화면에서 "조정 없음"을
오류로 보이지 않게 표현해 주시면 좋겠습니다.
