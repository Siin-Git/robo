@echo off
setlocal
cd /d "%~dp0.."
echo ========================================
echo ROBO ADVISOR - LOCAL PREVIEW
echo ========================================
echo.

where python >nul 2>&1 || (echo Python not found. Install Python 3.10+ &amp; add to PATH. &amp; exit /b 1)
where node >nul 2>&1 || (echo Node not found. Install Node 18+ ^(nodejs.org^) &amp; exit /b 1)

if not exist data\forward_local.db (
  echo Local DB not found.
  choice /M "Initialize local DB now"
  if errorlevel 2 exit /b 0
  python -m src.local.init || exit /b 1
)

echo Ensuring LOCAL test account...
python -m src.local.ensure_test_account


echo Profile:  LOCAL
echo Database: data/forward_local.db
echo FastAPI:  http://127.0.0.1:8000
echo Web:      http://localhost:3000
echo Live DB:  NOT USED
echo.

if not exist web\node_modules (
  echo Frontend dependencies missing.
  choice /M "Run npm install now"
  if not errorlevel 2 (
    pushd web
    call npm install || exit /b 1
    popd
  )
)

REM Prevent dev/prod chunk mismatch (e.g. Cannot find module './276.js'):
REM `next build` leaves production .next that `next dev` must not reuse.
if exist web\.next (
  echo Cleaning stale web\.next ^(prevents dev/prod chunk mismatch^)...
  rmdir /s /q web\.next
)

REM Fail fast on stale servers (never taskkill unrelated node processes).
netstat -ano | findstr "127.0.0.1:8000" | findstr "LISTENING" >nul && (echo Port 8000 already in use ^(stale backend?^). Stop the old uvicorn for this project first. & exit /b 1)
netstat -ano | findstr ":3000" | findstr "LISTENING" >nul && (echo Port 3000 already in use ^(stale Next dev?^). Stop the old next dev for this project first. & exit /b 1)

start "robo-api" cmd /k "set APP_PROFILE=local && set DATABASE_BACKEND=sqlite && python -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000"
start "robo-web" cmd /k "cd web && set NEXT_PUBLIC_APP_PROFILE=local && set FASTAPI_INTERNAL_URL=http://127.0.0.1:8000 && npm run dev"

timeout /t 8 >nul

echo Backend: checking http://127.0.0.1:8000/health ...
powershell -Command "try { Invoke-WebRequest http://127.0.0.1:8000/health -UseBasicParsing | Out-Null; Write-Host 'Backend: READY' } catch { Write-Host 'Backend: NOT YET READY (wait a moment)' }"
echo Frontend: checking http://localhost:3000 ...
powershell -Command "try { Invoke-WebRequest http://localhost:3000/login -UseBasicParsing | Out-Null; Write-Host 'Frontend: READY' } catch { Write-Host 'Frontend: NOT YET READY (wait a moment)' }"

echo Opening browser...
start http://localhost:3000/login
echo ========================================
echo Close both robo-api / robo-web windows or press Ctrl+C there to stop.
echo ========================================
endlocal
