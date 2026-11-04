# Yahoo session-date correction — 2026-10-05

## Correction and source evidence

`src/data/provider.py::_yahoo_daily_series` assigns a daily bar to its source
`meta.exchangeTimezoneName` IANA session date before dropping timezone information.
London 2026-09-18 00:00 BST = UTC 2026-09-17 23:00. The old parser stored the
1379.530029296875 USDKRW bar as 9/17, making 9/18 appear absent. DST-aware conversion
restores 9/18. No blanket +1-day correction or static GMT offset is used.
A one-day query boundary margin is filtered back to the requested session dates;
missing/invalid source timezone fails instead of guessing. Quote/adjusted-close
selection is unchanged. Domestic/US ETFs have no date change in the checked fixtures.

Session dates describe daily valuation inputs. The existing simulated fill's
`execution_at` date and actual `created_at` timestamp are distinct; this change
neither shifts order timestamps nor claims cross-market closes happened at the
same instant. KRW per USD FX converts existing unhedged USD price levels; native
KR prices and the existing IEF/TIP hedged proxies retain the existing rule. Those
proxies do not reproduce a real KRW hedged ETF or broker holding quantity.

## Identical-period replay and final demo

The old 3097 run and ledger are preserved. A new marked local SQLite environment
copies only its auth roster and original unexecuted design store via consistent
SQLite backup, retaining the same immutable 15 judgments, configurations, dates,
1억원 seed per account, 5bp costs and account IDs. No old orders/trades/NAV/prices
are copied. Full real-price collection covers 2026-08-04–10-02; it does not start
at MAX(stored date)+1. FX aside, the same-date raw levels for all 15 assets match
the previous capture exactly in the comparison interval (0 changed values).

**Final demonstrated window: 2026-09-16–10-02, FIXED_WINDOW, 11 common observations.**
9/18 is restored. 9/24–25 are confirmed KRX Chuseok closures for the Korean ETFs,
not a failed Yahoo fetch; common valuation is unavailable on those two dates.
`config/replay_sessions_20260916_20261002.json` records this narrowly scoped
calendar evidence. Outside reviewed closures an absent bar remains
SOURCE_OBSERVATION_MISSING (cause unconfirmed), never an assumed holiday.
Sources: [KRX calendar](https://open.krx.co.kr/contents/MKD/01/0110/01100305/MKD01100305.jsp),
[KRX 09/21 Chuseok notice](https://trn.krx.co.kr/index.jsp),
[NYSE 2026 calendar](https://www.nyse.com/publicdocs/nyse/ICE_NYSE_2026_Yearly_Trading_Calendar.pdf).
Neither holiday bars nor unknown gaps are interpolated. Graphs retain all internal
observations and explicit nulls on missing weekdays. Observed MDD is displayed;
its ranking remains withheld under the existing conservative weekday-gap rule.
Annual volatility/TE/IR remain unavailable with only 10 observed returns (<30).

A separate latest-10 replay is also complete: 2026-09-17–10-02. Its P003 return is
−0.78021148%, CORE −1.07684275%, difference +0.29663127%p, observed MDD −2.47622574%.
That is a different start valuation and investment date, not an identical-period
before/after comparison. The browser demo uses the 11-observation fixed window.

| P003, identical 9/16–10/2 window | Before | Corrected |
|---|---:|---:|
| Personal cumulative return | −0.69516694% | +0.21127061% |
| CORE return | −1.05969012% | +0.18845140% |
| Personal minus CORE | +0.36452318%p | +0.02281921%p |
| Observed MDD | −2.03842604% | −2.49590517% |
| Return rank | 6/15 | 11/15 |
| Observations per account | 10 | 11 |
| Latest personal NAV | 99,255,255.08원 | 100,161,240.09원 |
| Cash | 100,000원 | 100,000원 |

| P003 contribution, %p | Before | Corrected |
|---|---:|---:|
| Equity | −0.05643212 | +0.40421042 |
| Bonds | −0.24859473 | −0.24859473 |
| Alternatives | −0.51034077 | −0.29861488 |
| Themes | +0.12020068 | +0.35426981 |

The API contribution sum equals cumulative return. First-day purchase costs are
in the first recorded NAV; period performance is rebased to that NAV, consistent
with the existing calculator. They are not omitted from the cash/ledger.

| Participant | Before return | Corrected return | Rank |
|---|---:|---:|---:|
| P001 | -1.201668% | -0.710527% | 12 → 15 |
| P002 | -0.375560% | +0.382234% | 1 → 8 |
| P003 | -0.695167% | +0.211271% | 6 → 11 |
| P004 | -1.279688% | -0.335491% | 14 → 14 |
| P005 | -0.621613% | +0.375495% | 5 → 9 |
| P006 | -0.601817% | +0.418265% | 4 → 6 |
| P007 | -0.798001% | +0.249490% | 10 → 10 |
| P008 | -0.562862% | +0.500887% | 3 → 5 |
| P009 | -1.279406% | -0.166021% | 13 → 13 |
| P010 | -0.704331% | +0.522623% | 8 → 4 |
| P011 | -0.755621% | +0.414815% | 9 → 7 |
| P012 | -0.697979% | +0.594177% | 7 → 3 |
| P013 | -0.467698% | +0.795627% | 2 → 1 |
| P014 | -1.445152% | -0.062514% | 15 → 12 |
| P015 | -1.092112% | +0.658348% | 11 → 2 |

## Verification

- Whole backend: 589 passed, 0 failed/skipped, including disposable PostgreSQL 18
  on isolated port 50664 and SQLite; tests/backup excluded per existing CI scope.
- Provider regression: 11 offline original-response tests; London DST on/off,
  US DST on/off, Korean/US ETF labels, request boundaries and missing-zone failure.
- Frontend: 75 tests passed; production build/lint/type checks passed.
- Chrome E2E: desktop 1440 and mobile 390, 2 passed; portfolio/Frontier,
  disclosure open/close, ledger/cash, graphs/contributions, CORE/ranks,
  refresh/relogin and decision review. No page errors/horizontal overflow.
- Existing interior −50% MDD regression and 0/1/current/pending decision tests
  pass. Recovery/partial-run/forward-copy tests pass unchanged. Re-executing
  the new real-price run returns reused=true; all row counts remain unchanged.
- Corrected run: 15/15 READY and COMPLETE, 30 accounts, 268 orders/trades,
  2,948 holding rows, 330 NAV rows, 176 stored input levels. Every NAV equals
  holding value + cash. No synthetic price/NAV rows or production writes.
- Independent read-only audit: all 30 accounts have the expected 11 dates;
  fill/quantity/holding price/value reconciliation exact; cash-flow rounding
  error at most 2.98e−8원; P003 independently calculated contribution discrepancy
  1.2e−17. Personal report, contributions and ranking agree for all 15 users.

Two requested subagents inspected data/calculations and professor requirements
without modifying app code/data/settings. Final commit rechecks are recorded in
this run's private verification summary. Their findings were evaluated by the
main agent; no new financial threshold or admin architecture was introduced.

## Local demo and restart

- Corrected app: http://127.0.0.1:3099/dashboard, API 8099.
- Representative: capstone03@example.com; existing demo passwords retained only
  in /private/tmp/robo-session-corrected-data-20261005/accounts.md (not Git/PR).
- Data/run evidence/screens: /private/tmp/robo-session-corrected-data-20261005.
- Old 3097 data: /private/tmp/robo-competition-replay-f8q138c4, preserved.
- Worktree: /private/tmp/robo-session-dates-20261005.
- Browser has a separate private Chrome profile so 3073 cookies are preserved.

From this worktree:

```sh
.venv/bin/python scripts/competition_replay.py stop --directory /private/tmp/robo-session-corrected-data-20261005
.venv/bin/python scripts/competition_replay.py serve --directory /private/tmp/robo-session-corrected-data-20261005
```

Reproducible same-configuration replay (NEW temporary directory):

```sh
.venv/bin/python scripts/competition_replay.py fork --directory /private/tmp/NEW_SESSION_AUDIT --from-directory /private/tmp/robo-competition-replay-f8q138c4 --port 3099 --api-port 8099
.venv/bin/python scripts/competition_replay.py fetch --directory /private/tmp/NEW_SESSION_AUDIT --start 2026-08-04 --end 2026-10-02
.venv/bin/python scripts/competition_replay.py prepare --directory /private/tmp/NEW_SESSION_AUDIT --start 2026-09-16 --end 2026-10-02
.venv/bin/python scripts/competition_replay.py run --directory /private/tmp/NEW_SESSION_AUDIT
```

A sealed run rejects another window. Ordinary daily execution still cannot bypass
account_gate or replay scope. This demo does not register a forward scheduler,
set operating T0 or satisfy real 3/6-month observation periods.

## Professor requirements: independent check

Professor transcription text was not found in the supplied conversation/files.
The classifications below refer to the user's explicit requirements, not an
invented transcript. Existing ledger 09e92ad and research 66df9cc are in this branch.

| Requirement | Status | Evidence / limit |
|---|---|---|
| Original judgment / selected Frontier point | Implemented and connected | onboarding_service.complete → decision_service.capture; PortfolioDecision/BasePortfolioSelection store immutable weights/expectations/units/horizon/Frontier ID/version and model/data hashes; /me/decisions/{id}/review → /review |
| Whole historical Frontier curve reproduction | Definition pending | Selected point/expectations are stored; /portfolio currently renders the current model curve and summary. Use /review for the recorded initial expectation |
| Portfolio's selected ETF/assets daily tracking | Implemented and connected (local replay); real forward data pending | prices_daily/trades/holdings_daily/nav_daily → ledger_read_service/performance_report → dashboard/ledger/contributions |
| User revision review/history | Implemented and connected | PortfolioChoice; decision_service.review/choose; /me/portfolio/choices; /review. KEEP/ADJUST is a configuration decision, not order approval |
| Internal administrator review of another user's judgment with recorded rationale | Unimplemented; responsibility definition pending | /me decisions enforce ownership; /admin has no separate revision API/UI. No duplicate admin feature added here |
| Basic user/admin authorization | Implemented and connected | User.role, authz.require_admin/enforce_owner; /admin authorization. Local replay admin ledger linkage is unimplemented (admin reads auth DB) |
| Expected-versus-actual numeric comparison | Definition pending / actual data pending | Matching duration alone is insufficient; units/definitions/costs/sampling/benchmark must also match. Replay is excluded from original-design actual review |

Do not expand these into tracking every company inside every ETF. Selected asset
tracking is connected. Internal reviewer permissions/records need agreement before
implementation. The current demo shows stored initial judgment and user revision
support; it does not claim internal administrator revision is complete.

## Operating impact and required recovery procedure (not executed)

Read-only repository check: origin/release/public-operation b6add63 still contains
the old UTC-normalization parser. That establishes exposure if the deployed app/job
uses this commit; actual Render runtime commit/DB matching is still unverified.
This task does not query or replace operating prices and cannot certify which
stored production rows are wrong. Existing source strings do not retain raw bar
IANA timezone/timestamps, so a DB date alone cannot prove correctness.

Potential scope: London-currency bars during BST (including first/last requested
boundary bars), and any instrument whose local daily session crosses a UTC date.
The tested Seoul/New York daily bars do not shift. Derived unhedged KRW levels,
trades/quantities/NAV/contributions/ranks may be affected by misaligned FX. Frozen
artifacts generated with the same provider require a separate data-version audit;
do not mutate existing original judgments or recompute their initial expectations.

Before any approved operational repair:

1. Confirm Render/Actions deployed commit, database identity and pricing-source
   coverage privately; inventory every asset/date/source and freeze a consistent
   isolated backup of raw inputs, targets, orders, trades, holdings and NAV.
2. Re-fetch the complete potentially affected date range for every required native
   asset plus FX with raw response/timezone/hash/version evidence. Starting at
   MAX(date)+1 cannot fix existing history. Compare session labels/values against
   originals and identify downstream affected dates/rows.
3. Reconstruct inputs and valuations in a disposable copy using the same engine.
   Distinguish preserving recorded execution quantities for a corrected valuation
   from re-executing a counterfactual strategy (which can change quantities/costs).
   Agree on correction/version policy; never silently rewrite executed fills.
4. Check NAV/cash/holding identity, per-period contributions and common-period
   ranks, price gaps, restart/idempotency and future continuation. Keep the old
   ledger/run available for audit and rollback.
5. Only after separately approved correction/deployment promote the reviewed data
   version; preserve immutable judgment dates, operating T0 and actual timestamps.

No merge/deployment, operating DB rewrite/replay, scheduler/T0 change, PR12 change
or new market/hedge rule was performed. Draft PR #1 is updated with these limits.
