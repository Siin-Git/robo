@echo off
rem ===========================================================================
rem Capstone demo: daily forward ledger run (called by Windows Task Scheduler).
rem
rem run_daily is idempotent and driven by data, not by the clock. Running it
rem several times a day is safe, and a day skipped because the laptop was off
rem is caught up on the next run. Duplicate runs are blocked by scheduled_jobs.
rem
rem On the first day of a month this also runs the monthly rebalance, in this
rem file rather than a second scheduled task so the order is guaranteed: the
rem monthly decision needs the previous day's close, which run_daily fetches.
rem A dry run is logged first, so the plan sits next to the result.
rem
rem Output is appended to logs\forward_daily.log (covered by *.log in
rem .gitignore). ASCII only: cmd reads this file in the OEM code page.
rem ===========================================================================
setlocal

rem --- Environment: point the forward engine at the capstone design DB ------
set "ROOT=%~dp0.."
set "APP_PROFILE=local"
set "CAPSTONE_DEMO=1"
rem DATABASE_BACKEND is intentionally NOT set here. It comes from .env.local so
rem that one file decides SQLite vs PostgreSQL for the batch, the API and the
rem dev scripts alike. get_backend() falls back to sqlite when it is absent.
rem The banner printed by run_daily always says which database was used.

cd /d "%ROOT%" || exit /b 1
if not exist "logs" mkdir "logs"
set "LOG=logs\forward_daily.log"
set "PY=.venv\Scripts\python.exe"

if not exist "%PY%" (
  echo [%DATE% %TIME%] ERROR: %PY% not found >> "%LOG%"
  exit /b 1
)

echo. >> "%LOG%"
echo ======================================================== >> "%LOG%"
echo RUN START %DATE% %TIME% >> "%LOG%"
echo ======================================================== >> "%LOG%"

rem --- 1. Daily: prices, orders, executions, valuation ----------------------
"%PY%" -m src.forward.run_daily >> "%LOG%" 2>&1
set "CODE=%ERRORLEVEL%"
echo run_daily EXIT=%CODE% >> "%LOG%"

rem --- 2. Monthly rebalance on the first of the month -----------------------
rem Ask Python for the day of month: %DATE% formatting depends on the locale.
"%PY%" -c "import datetime,sys; sys.exit(0 if datetime.date.today().day==1 else 1)"
if not errorlevel 1 (
  echo. >> "%LOG%"
  echo -------- first of month: monthly rebalance -------- >> "%LOG%"
  rem Preview first so the plan is recorded next to the result.
  "%PY%" -m src.forward.run_monthly --dry-run >> "%LOG%" 2>&1
  echo -------- executing -------- >> "%LOG%"
  "%PY%" -m src.forward.run_monthly >> "%LOG%" 2>&1
  echo run_monthly EXIT=%ERRORLEVEL% >> "%LOG%"
  echo   orders take effect on the next trading day; they execute at that >> "%LOG%"
  echo   close on the following run, so there is a day to review them. >> "%LOG%"
)

rem --- 3. Read-only summary into the same log -------------------------------
"%PY%" scripts\dev_ledger_report.py >> "%LOG%" 2>&1

echo RUN END %DATE% %TIME% >> "%LOG%"
endlocal & exit /b %CODE%
