# 프론트엔드 연동 안내: 성과 기여도와 Efficient Frontier

기준 브랜치는 `feat/lab-meeting`, 백엔드 작업 브랜치는
`feat/performance-api`입니다. 아래 API는 로그인 세션 쿠키를 사용하며 숫자형
수익률과 기여도는 퍼센트가 아닌 소수입니다. 예를 들어 `0.052`는 화면에서
`5.2%` 또는 `5.2%p`로 표시합니다.

## 1. 테마 적용 전후 Efficient Frontier 위치

### 온보딩 미리보기

```http
POST /api/v1/me/onboarding/preview
Content-Type: application/json

{
  "frontier_id": "F002",
  "theme_ids": ["ai", "semiconductor"]
}
```

### 저장된 포트폴리오 요약

```http
GET /api/v1/me/portfolio/summary
```

두 응답 모두 `frontier_position`을 포함합니다.

```json
{
  "frontier_position": {
    "base": {
      "label": "base",
      "frontier_id": "F002",
      "expected_return": 0.06,
      "volatility": 0.1,
      "on_frontier": true,
      "nearest_frontier_id": "F002",
      "nearest_expected_return": 0.06,
      "nearest_volatility": 0.1,
      "volatility_delta": 0.0,
      "return_gap": 0.0,
      "method": "exact_frontier_point"
    },
    "personalized": {
      "label": "personalized",
      "frontier_id": null,
      "expected_return": null,
      "volatility": 0.12,
      "on_frontier": false,
      "nearest_frontier_id": "F002",
      "nearest_expected_return": 0.06,
      "nearest_volatility": 0.1,
      "volatility_delta": 0.02,
      "return_gap": null,
      "method": "nearest_frontier_by_volatility"
    }
  }
}
```

- `base`: 테마 적용 전 기본 포트폴리오입니다.
- `personalized`: 테마 적용 후 포트폴리오입니다.
- `volatility_delta`: 가장 가까운 Frontier 지점과의 변동성 차이입니다.
- `return_gap`: 같은 변동성의 Frontier 수익률과 비교한 차이입니다. 기대수익률을
  계산할 수 없으면 `null`입니다.
- `method=unavailable`이면 위치를 계산할 데이터가 아직 없는 상태입니다.

## 2. 자산별 누적 수익 기여도

```http
GET /api/v1/me/performance/contributions?period=ALL
```

`period`는 `1M`, `3M`, `6M`, `1Y`, `ALL` 중 하나입니다.

```json
{
  "status": "OK",
  "period": "ALL",
  "start": "2026-09-07",
  "end": "2026-09-30",
  "observations": 18,
  "cumulative_return": 0.052,
  "assets": [
    {
      "asset_id": "us_equity",
      "group": "equity",
      "cumulative_contribution": 0.031,
      "average_weight": 0.4,
      "price_return": 0.068
    },
    {
      "asset_id": "costs",
      "group": "costs",
      "cumulative_contribution": -0.001,
      "average_weight": null,
      "price_return": null
    }
  ],
  "history": [
    {
      "date": "2026-09-30",
      "cumulative_return": 0.052,
      "contributions": {
        "us_equity": 0.031,
        "costs": -0.001,
        "unexplained": 0.0
      }
    }
  ],
  "reconciliation": {
    "contribution_total": 0.052,
    "difference": 0.0,
    "reconciled": true
  },
  "quality": {
    "unresolved_intervals": 0,
    "stale_observations": 0,
    "missing_nav_dates": 0,
    "benchmark_complete": true
  },
  "method": "linked_asset_pnl_over_opening_nav"
}
```

프론트 표시 규칙:

- `assets`는 누적 막대 또는 순위에 사용합니다.
- `history`는 날짜별 누적 영역 차트에 사용합니다.
- `costs`는 거래비용의 음수 기여도입니다.
- `unexplained`는 누락된 보유내역 등으로 자산에 귀속할 수 없는 차이입니다.
- `reconciled=false`이거나 `quality.unresolved_intervals > 0`이면 경고 상태로
  표시하고 특정 자산의 성과로 단정하지 않습니다.
- `status=INSUFFICIENT_HISTORY`이면 빈 상태를 표시합니다.
- `status=SHORT_HISTORY`이면 누적 기여도는 표시할 수 있지만 연환산 위험지표는
  아직 제공되지 않을 수 있습니다.

## 3. 백엔드 1 영속 장부 조회

```http
GET /api/v1/me/performance/ledger?start=2026-09-01&end=2026-09-30
```

`start`와 `end`는 선택 사항이며 `YYYY-MM-DD` 형식입니다. 응답은 서버 메모리가
아니라 백엔드 1이 DB에 기록한 `nav_daily`, `holdings_daily`, `orders`, `trades`,
`prices_daily`에서 조회합니다.

```json
{
  "contract_version": "ledger-read-v1",
  "participant_id": "P001",
  "account": {
    "account_id": "A-P001-PERSONAL",
    "account_type": "personal",
    "status": "active",
    "inception_date": "2026-09-07"
  },
  "as_of": "2026-09-30",
  "snapshots": [
    {
      "date": "2026-09-30",
      "nav": 105200000,
      "cash_balance": 3200000,
      "daily_return": 0.0012,
      "cumulative_return": 0.052,
      "nav_status": "OK",
      "stale_price_flag": false,
      "holdings": [
        {
          "asset_id": "us_equity",
          "quantity": 25.3,
          "price": 152000,
          "price_date": "2026-09-30",
          "price_source": "yahoo",
          "price_status": "current",
          "market_value": 3845600,
          "weight": 0.0366
        }
      ]
    }
  ],
  "orders": [
    {
      "order_id": "O901",
      "asset_id": "us_equity",
      "side": "sell",
      "target_weight": 0.35,
      "effective_at": "2026-10-01",
      "status": "pending",
      "action_required": true,
      "alert_type": "sell_required"
    }
  ],
  "order_status_summary": {
    "pending": 1,
    "executed": 4,
    "cancelled": 0
  },
  "trades": []
}
```

가격 상태:

- `current`: 평가일 종가를 사용했습니다.
- `carried_forward`: 최근 유효 종가를 이어서 사용했으며 허용 기간 안입니다.
- `stale`: 오래된 가격으로 평가되어 주의가 필요합니다.
- `missing`: 연결 가능한 가격 기록이 없습니다.

NAV 상태:

- `OK`: 정상 평가입니다.
- `STALE_PRICE`: 하나 이상의 오래된 가격이 포함됐습니다.
- `NAV_INCOMPLETE`: 평가에 필요한 데이터가 부족합니다.

주문 알림은 `action_required=true`인 주문만 노출합니다.
`alert_type=buy_required`는 추가 매수, `sell_required`는 매도 필요 알림입니다.
`executed`와 `cancelled` 주문은 이력에는 표시할 수 있지만 행동 알림에서는 제외합니다.

## 4. TypeScript 최소 타입

```ts
type Period = "1M" | "3M" | "6M" | "1Y" | "ALL";

type ContributionAsset = {
  asset_id: string;
  group: string;
  cumulative_contribution: number;
  average_weight: number | null;
  price_return: number | null;
};

type OrderAlert = {
  order_id: string;
  asset_id: string;
  side: "buy" | "sell";
  status: "pending" | "executed" | "cancelled";
  action_required: boolean;
  alert_type: "buy_required" | "sell_required" | null;
};

type PriceStatus = "current" | "carried_forward" | "stale" | "missing";
type NavStatus = "OK" | "STALE_PRICE" | "NAV_INCOMPLETE";
```

## 5. 프론트 연동 체크리스트

1. 요청에 기존 로그인 쿠키를 포함합니다.
2. 퍼센트 표시는 API 숫자에 `100`을 곱합니다.
3. 기여도 합계가 아니라 `reconciliation.reconciled`를 대사 기준으로 사용합니다.
4. `null`을 `0`으로 바꾸지 말고 데이터 없음으로 표시합니다.
5. `costs`와 `unexplained`를 일반 투자자산과 다른 색상으로 구분합니다.
6. 주문 알림은 `action_required`와 `alert_type`으로 결정합니다.
7. 날짜 범위가 잘못되면 `400`, 로그인하지 않으면 `401`, 다른 사용자의
   participant API에 접근하면 `403`이 반환됩니다.

Swagger에서는 로컬 서버 실행 후 `http://127.0.0.1:8000/docs`에서 응답을 직접
확인할 수 있습니다.
