# Dashboard detail disclosure UI — 2026-10-05

UI source: cc9bfe8, integrated as 02cf3eb. Current midpoint demo: 3099 on validated code41b4bdd; see LOCAL_COMPETITION_REPLAY.md. The original isolated UI checkout is preserved.

The dashboard now leads with performance, CORE comparison, charts and contributions. Replay metadata is a compact source/period strip with a closed “시연 정보” disclosure. Risk eligibility, calculation definitions and supporting data are available in closed disclosures. Holdings, orders and rebalance details are grouped below the charts; the balance-summary link opens that section. Empty-state operational details remain expanded.

The visible replay label, incomplete-processing notice, synthetic-data notice, missing-data qualification on MDD, and existing chart gaps remain. No return, ranking, replay, market-calendar or trading calculation was changed. The separate session-date correction repairs the FX date; this UI commit itself contains no financial change.

## Preview

Current demo: http://127.0.0.1:3099/dashboard (11 observations, corrected FX session dates). Historical UI-only preview3101 is not the midpoint demo.
Current API: http://127.0.0.1:8099. Data: /private/tmp/robo-session-corrected-data-20261005. The previous3101 preview used8097; it is preserved as an earlier UI-only check. Test account identifiers and passwords remain solely in the existing private local account file; none are copied here.

Restart the final demo with the existing launcher (preserves the same DB):

```sh
cd /private/tmp/robo-session-dates-20261005
.venv/bin/python scripts/competition_replay.py serve --directory /private/tmp/robo-session-corrected-data-20261005
```

The launcher reuses its own running API/web processes. Stop/recovery and the persistent private backup are documented in [LOCAL_COMPETITION_REPLAY.md](LOCAL_COMPETITION_REPLAY.md).
For a standalone source checkout, install web/package-lock.json with npm ci.

## Validation

- Frontend: 75 tests passed in 17 files (current integrated code). Updated the existing ReplayNotice regression to cover a visible source badge and incomplete-run notice with closed supporting details.
- Final production build, lint/type checking passed.
- Browser: capstone03; source badge, disclosure open/close, keyboard activation, balance-to-ledger link, corrected +0.21% / +0.19% / +0.02%p / -2.50% values, 11 observations and rank11/15.
- Responsive: 390px viewport, document width 390px, no horizontal page overflow; risk disclosure works.
- Current screenshots: /private/tmp/robo-session-corrected-data-20261005/screens/dashboard-1440.png and dashboard-390.png. Earlier UI-only captures are not current figures.

UI integration is complete in Draft PR #1 with the corrected date/replay changes. No merge/deployment. Restart the final3099 using LOCAL_COMPETITION_REPLAY.md; the earlier 3101 UI preview remains historical only.
