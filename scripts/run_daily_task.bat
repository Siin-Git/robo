@echo off
rem ===========================================================================
rem Capstone demo: daily forward ledger run (called by Windows Task Scheduler).
rem
rem run_daily is idempotent and driven by data, not by the clock. Running it
rem several times a day is safe, and a day skipped because the laptop was off
rem is caught up on the next run. Duplicate runs are blocked by scheduled_jobs.
rem
rem Output is appended to logs\forward_daily.log (covered by *.log in
rem .gitignore). ASCII only: cmd reads this file in the OEM code page.
rem ===========================================================================
setlocal

rem --- Environment: point the forward engine at the capstone design DB ------
set "ROOT=%~dp0.."
set "APP_PROFILE=local"
set "CAPSTONE_DEMO=1"
set "DATABASE_BACKEND=sqlite"

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

"%PY%" -m src.forward.run_daily >> "%LOG%" 2>&1
set "CODE=%ERRORLEVEL%"
echo run_daily EXIT=%CODE% >> "%LOG%"

rem Read-only summary into the same log.
"%PY%" scripts\dev_ledger_report.py >> "%LOG%" 2>&1

echo RUN END %DATE% %TIME% >> "%LOG%"
endlocal & exit /b %CODE%
