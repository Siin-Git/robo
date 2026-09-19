# Final Demo Verification

API audit: PASS. UI values rounded to two decimals; full precision in `.work/capstone_audit.json`.

## Overall Result: PASS

- Actual Chrome verification: **13/13 accounts PASS** through Login, Dashboard, refresh, Ranking, Detail, allocation and Logout in the same browser context.
- Each rendered KPI checked against the independent audit; full Recharts input arrays checked against all API NAV points for each participant, on Dashboard and Detail.
- All 13 table rows checked for each of the five sort criteria; rank numbering and actual Top 3 CSS/background checked.
- Requested scenarios A-E and mobile viewport checks: PASS; no browser pageerror.
- Ranking deliberately omits a separate CORE column; its API core_return equals Dashboard/Detail. Volatility verified via its sort selection.
- Focused backend regression: 25 passed. Final Chrome suite: 3 passed (including the 13-account loop). TypeScript/production build: PASS.
- Direct SQLite audit: stored cumulative/daily return formulas have zero error against stored NAV. API NAV uses the existing Numeric(24,8) conversion (maximum raw-storage rounding 4.99e-9 NAV units); chart data exactly equals API data.
- No new financial engine, strategy, account model, attribution or rebalancing introduced.

| Account | Participant | Themes | Return | CORE | Excess | MDD | Volatility | Sharpe | Auth/logout |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| capstone01@example.com | P001 | semiconductor + ai | +13.15% | +5.38% | +7.77%p | -6.32% | 16.01% | 1.74 | PASS |
| capstone02@example.com | P002 | defense + nuclear | +4.71% | +5.38% | -0.67%p | -3.82% | 7.85% | 1.30 | PASS |
| capstone03@example.com | P003 | power_grid + cybersecurity | +6.50% | +5.38% | +1.11%p | -2.25% | 4.12% | 3.31 | PASS |
| capstone04@example.com | P004 | ai + robotics | +5.45% | +5.38% | +0.07%p | -3.03% | 5.77% | 2.01 | PASS |
| capstone05@example.com | P005 | biotech + nuclear | -2.07% | +5.38% | -7.46%p | -3.80% | 4.48% | -0.99 | PASS |
| capstone06@example.com | P006 | semiconductor + defense | +12.37% | +5.38% | +6.99%p | -4.87% | 11.74% | 2.20 | PASS |
| capstone07@example.com | P007 | cloud_data_center + ai | +7.42% | +5.38% | +2.04%p | -4.16% | 8.86% | 1.78 | PASS |
| capstone08@example.com | P008 | robotics + biotech | -2.55% | +5.38% | -7.93%p | -6.25% | 9.61% | -0.53 | PASS |
| capstone09@example.com | P009 | defense + power_grid | +8.32% | +5.38% | +2.94%p | -2.77% | 5.65% | 3.08 | PASS |
| capstone10@example.com | P010 | nuclear + semiconductor | +7.39% | +5.38% | +2.01%p | -4.85% | 11.60% | 1.38 | PASS |
| capstone11@example.com | P011 | cybersecurity + cloud_data_center | +4.69% | +5.38% | -0.69%p | -2.80% | 4.89% | 2.04 | PASS |
| capstone12@example.com | P012 | biotech + cloud_data_center | -0.65% | +5.38% | -6.04%p | -6.35% | 10.24% | -0.09 | PASS |
| capstone13@example.com | P013 | robotics + power_grid | +3.22% | +5.38% | -2.16%p | -2.00% | 3.37% | 2.04 | PASS |

## Data

- Frozen CORE V0.3 allocations exactly equal across 13 participants.
- 2026-04-01 to 2026-09-11: 118 NAV points, 117 daily returns.
- Identical ordered date arrays and CORE NAV arrays. Start NAV = 100.
- No duplicate dates, nulls, NaN, infinity, non-positive NAV or negative weights.
- Two seeded themes each at 7.5%; portfolio weights sum to 1 within 1e-12.

## Independent formulas

Python math/statistics applied directly to returned NAV, without calling application metric functions.
- Return = final NAV / initial NAV - 1.
- Excess = personal Return - CORE Return; displayed in percentage points.
- MDD = min(NAV / running maximum NAV - 1).
- Volatility = sample standard deviation of daily returns (ddof=1) * sqrt(252).
- Sharpe = mean daily return / sample standard deviation * sqrt(252), risk-free rate = 0.
- Demo API requires at least 31 NAV points (30 returns); shared perf_metrics itself permits 30 NAV points.
- Absolute tolerance: 1e-12; no relative tolerance.

| Metric | Maximum absolute error |
|---|---:|
| nav | 0 |
| cumulative_return | 0 |
| core_return | 0 |
| excess_return | 0 |
| mdd | 6.66e-16 |
| volatility | 1.53e-16 |
| sharpe | 3.71e-14 |

## Independent full rankings

| Basis | Top 3 |
|---|---|
| return | 참여자 01 -> 참여자 06 -> 참여자 09 |
| excess | 참여자 01 -> 참여자 06 -> 참여자 09 |
| mdd | 참여자 13 -> 참여자 03 -> 참여자 09 |
| volatility | 참여자 13 -> 참여자 03 -> 참여자 05 |
| sharpe | 참여자 03 -> 참여자 09 -> 참여자 06 |

All 13 positions and ranks checked. Return/Excess/Sharpe descending; MDD closest to zero first; Volatility ascending.

## Corrections

1. Recompute daily returns from the displayed NAV before calling existing perf_metrics. Removes the prior maximum Sharpe mismatch of 4.54e-9 caused by separately rounded stored daily returns.
2. Small deterministic irregularity applied only to intermediate synthetic NAV. Maximum level change 0.2335241%; all endpoints, cumulative returns, excess returns, dates, accounts, themes and allocations preserved. Backup: `.work/capstone_pre_validation.db`. Seed generator updated consistently.
3. Demo charts connect daily observations linearly instead of interpolating smooth curves.
4. Added rounding clarification: Excess uses unrounded returns; subtracting rounded displayed numbers can differ by 0.01 percentage point.

## Limits

- Geometric active-return code remains in the original non-demo implementation. Demo pages use only the comparison API; browser network requests are checked.
- Expected/optimization Sharpe is not used.
- All pages explicitly label synthetic demo data. This is not actual forward-test performance or an ETF/transaction-ledger simulation.
- 7 participants beat CORE and 6 underperform; return gaps are non-uniform; risk rankings differ.

## Reproduce

```sh
.venv/bin/python scripts/verify_capstone.py
.venv/bin/python -m pytest tests/api/test_capstone_demo.py tests/forward/test_performance_report.py tests/api/test_auth.py -q
cd web
npx playwright test --config playwright.audit.config.ts --reporter=line
```
