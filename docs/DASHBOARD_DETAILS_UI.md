# Dashboard detail disclosure UI — 2026-10-05

Base: competition replay 4f18dde. Branch: feat/dashboard-details-ui.

The dashboard now leads with performance, CORE comparison, charts and contributions. Replay metadata is a compact source/period strip with a closed “시연 정보” disclosure. Risk eligibility, calculation definitions and supporting data are available in closed disclosures. Holdings, orders and rebalance details are grouped below the charts; the balance-summary link opens that section. Empty-state operational details remain expanded.

The visible replay label, incomplete-processing notice, synthetic-data notice, missing-data qualification on MDD, and existing chart gaps remain. No return, ranking, replay, market-calendar or trading calculation was changed. This does not repair the FX gap discussed separately.

## Preview

http://127.0.0.1:3101/dashboard (development server with hot reload).
Uses the existing local replay API at http://127.0.0.1:8097 and its existing test data. That API must remain running. Test account identifiers and passwords remain solely in the existing private local account file; none are copied here.

Restart from this checkout's web directory:

```sh
NEXT_PUBLIC_APP_PROFILE=local NEXT_PUBLIC_CAPSTONE_DEMO=1 NEXT_PUBLIC_LAB_MEETING=1 FASTAPI_INTERNAL_URL=http://127.0.0.1:8097 NEXT_DIST_DIR=.next-ui-dev ./node_modules/.bin/next dev -p 3101 -H 127.0.0.1
```

This isolated checkout uses a local node_modules symlink to the original replay checkout. For a standalone checkout, install from web/package-lock.json with npm ci.

## Validation

- Frontend: 74 tests passed in 17 files. Updated the existing ReplayNotice regression to cover a visible source badge and incomplete-run notice with closed supporting details.
- Final production build, lint/type checking passed.
- Browser: capstone03; source badge, disclosure open/close, keyboard activation, balance-to-ledger link, unchanged -0.70% / -1.06% / +0.36%p / -2.04% values.
- Responsive: 390px viewport, document width 390px, no horizontal page overflow; risk disclosure works.
- Screenshots: /private/tmp/robo-dashboard-ui-desktop.png and /private/tmp/robo-dashboard-ui-mobile.png.

Only local UI changes are committed. No push, merge or deployment. To integrate, fetch this local checkout and cherry-pick the UI commit onto the current deployment/integration branch after checking overlapping frontend changes.
