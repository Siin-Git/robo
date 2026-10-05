# Local internal price tracking — 2026-10-05

## Problem and scope

The user requested automatic real-price tracking in the separate 3103 admin environment. That environment had an empty original design price store and a separate frozen historical replay ledger. The cloud daily-forward run 37250327467 was scheduled for 07:30 KST but started at 10:09 KST and failed its Korean intraday guard before collecting anything. The deployed head remained b6add63, not the corrected replay/internal-tracking commits.

Primary journey: hourly collector → completed Yahoo sessions → exact-date KRW levels in the existing design DB → the existing admin report (15-second polling). The frozen replay ledger, immutable decisions, review notes, orders, holdings and NAV remain unchanged. This is price observation tracking, not activation of the 15-person trading competition.

## Implementation decisions

- Use the existing Yahoo session-date parser, existing incremental price store and existing currency conversion rules. Current session quotes are filtered by source IANA timezone and vendor regular-session end plus a 30-minute buffer. FX waits until its source calendar date has ended. Missing close metadata waits conservatively; no guessed same-day close.
- Local observation mode never forward-fills a missing price or FX day. Native KRW / existing hedged inputs can arrive independently; USD assets wait for observed FX on the same date. The ordinary daily engine retains its default alignment behavior.
- The collection date comes from the current KST clock at each run. First collection starts at the earliest immutable decision effective date; later collection starts after each asset's last stored date. Prior prices are not rewritten, and replay history is never imported.
- Successful empty responses and pending intraday bars are normal waiting. Transport/invalid-data errors remain failures and list failed assets; successful assets may still be retained for the next retry.
- The worker accepts only the explicitly selected local SQLite design DB. A SQLite write authorizer additionally denies writes outside prices_daily. A per-target lock prevents concurrent copies. Before its first collection it creates a private persistent SQLite backup outside /tmp. Every completed collection also atomically refreshes a private latest-design.db backup, preserving new observations if the temporary serving directory is later removed.
- Use a uniquely named hourly launchd agent rather than modify the original 3073 schedule or cloud Actions. It runs at minute 17 and on login/load. The Mac must be awake and online. The existing 3103 API/frontend need no restart and already poll the report every 15 seconds.

## Local commands

Use the persistent project Python environment and this checkout's scripts/tracking_price_schedule.py:

- `run --directory /private/tmp/robo-internal-tracking-local-20261005`
- `status --directory /private/tmp/robo-internal-tracking-local-20261005`
- `plan --directory /private/tmp/robo-internal-tracking-local-20261005`
- `install --directory /private/tmp/robo-internal-tracking-local-20261005`
- `pause --directory /private/tmp/robo-internal-tracking-local-20261005`

The private `.local/tracking-prices-<target hash>/` contains the first backup, latest collection status, scheduler logs and planned plist. These are ignored by Git. The source data directory remains a local temporary directory: if it is removed the collector fails without silently creating an empty replacement. The existing separately frozen demo backups remain the recovery reference.

## Acceptance / verification

Regression cases cover delayed intraday execution, close buffer boundaries, US DST, FX day boundary, absent close metadata, exact-date conversion, holidays, partial fetch failures, restart/repeated incremental calls, no fabricated missing dates, data-directory targeting and forbidden order writes. Real-source verification checks published response session metadata, not synthetic timestamps.

No operating DB credentials, cloud settings, migration, shared branch merge or deployment changes are included. The cloud schedule failure is evidence of a separate production issue; this local scheduler does not repair it. The rejected remote read-only Actions dispatch was not executed or bypassed.

## Verified outcome

- Baseline-wide backend run: 596 passed, 16 skipped (optional PostgreSQL environments not configured), 23 existing dependency warnings, 174.13 seconds. After the final local-path and durable-backup additions, all 64 focused price/date/market-guard tests passed. No frontend files/contracts changed; frontend build/browser tests were not repeated in this price-only change.
- Public Yahoo responses for Korean ETF, US ETF and FX were read at 10:58 KST. Latest completed observations were 2026-10-02; the active 2026-10-05 FX bar was excluded.
- Actual 3103 collector ran at 11:05 KST with status OK, 0 failed assets, 0 new points. The earliest original decision effective date is 2026-10-05, so older prices were not imported to imitate post-confirmation observations.
- The uniquely named com.robo.tracking-prices.bd703e87c4c0 LaunchAgent was registered for minute 17 of every hour. Its real RunAtLoad execution at 11:06 KST completed with exit 0, normal empty waiting and no failed assets. This confirms registration and an actual background invocation, not a future session's new-row arrival.
- Immutable decision, review event, order, trade, holding and NAV row fingerprints matched before/after across portfolio_design.db, replay_ledger.db and capstone_demo.db. No 3099/3073/Neon or original scheduler changes.
- Code and scheduler interpreter paths are outside /tmp; serving data remains the explicitly selected 3103 directory. The durable Python environment is the existing robo/.venv, not a temporary installation.
- A repeated real collection at 11:08 KST again returned OK with no new completed prices. Both the first backup and latest-design.db passed SQLite integrity checks, retained all 16 decisions, and had private 0600 permissions.
- First operational attempt rejected an empty explicit URL in the demo configuration; the target resolver was corrected to use the app's documented CAPSTONE_DATA_DIR fallback only for explicitly local SQLite. A regression test covers it; no data changed during that failed attempt.
- AI implemented the collector and tests; deterministic tests, real-source reads, SQLite fingerprint comparison and launchctl process state independently establish the claims above. Future real-price insertion still awaits a newly completed source session.
