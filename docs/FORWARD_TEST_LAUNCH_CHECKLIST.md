# Forward Test Launch Checklist

Run every item before registering real participants. All commands run from `robo-advisor/`.

```text
[ ] APP_PROFILE=live                                   (profile banner shows LIVE + data/forward_test.db)
[ ] Live DB clean                                      (participants=0, views=0, orders=0, trades=0)
[ ] Demo participants = 0                              (preflight: Demo contamination NONE)
[ ] Demo views = 0
[ ] Benchmark version = CORE_V0.3                      (outputs/frozen/CORE_V0.3/weights.json present)
[ ] Theme universe = THEME_UNIVERSE_V0.1               (9 active + optical_networking inactive)
[ ] benchmark_model_date recorded                      (system_status.json)
[ ] snapshot_date recorded                             (system_status.json)
[ ] forward_test_inception_date unset before launch    (null until FORWARD_TEST_INCEPTION_SET)
[ ] latest market data valid                           (preflight freshness PASS)
[ ] participant registration complete
[ ] no retroactive orders                              (execution_at >= effective_at, preflight PASS)
[ ] transaction cost = 5bps                            (config/forward_v0.yaml)
[ ] view cutoff verified                               (preflight schedule test PASS)
[ ] execution rule verified                            (preflight timing test PASS)
[ ] daily run dry-run PASS                             (APP_PROFILE=live run_daily)
```

## Clean re-initialization procedure

```bash
python scripts/archive_prelaunch_live_db.py --profile live   # copy + sha256, source untouched
# verify archive JSON, then delete data/forward_test.db manually
APP_PROFILE=live python -m src.forward.init_forward_test   # refuses if history exists
APP_PROFILE=live python -m src.forward.preflight           # expect READY TO LAUNCH: YES
```

There is intentionally no force-reset flag. A DB that already contains
trades/NAV/views/participants is never reinitialized in place.

## Launch flow (after checklist)

1. `participants add --name ... --join-date YYYY-MM-DD` (creates core+personal accounts, inception orders pending)
2. `run_daily` (executes at next available closes, anchors NAV=100, sets first execution)
3. `views submit` before Friday 18:00 KST for next-week effectiveness
4. `run_weekly --week YYYY-MM-DD` (Friday batch), `generate_briefing`
5. `run_monthly` on month turn (risk refresh + core rebalance)
