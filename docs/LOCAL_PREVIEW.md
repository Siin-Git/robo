# Local Web Preview (Phase 3D.1)

One-command local website on your own PC. **Live DB is never touched** —
all writes go to `data/forward_local.db`.

## Quick Start (Windows)

```powershell
cd robo-advisor
.\scripts\start_local.ps1
# or: python scripts/start_local.py
```

Browser opens to `http://localhost:3000/login`.

## What it does

1. Checks `python`/`node`/`npm`
2. Creates `data/forward_local.db` if missing (`python -m src.local.init`)
3. Starts FastAPI `127.0.0.1:8000` (`APP_PROFILE=local`, `Secure=false`)
4. Starts Next.js `localhost:3000` (`FASTAPI_INTERNAL_URL=http://127.0.0.1:8000`)
5. Polls `/health` + frontend, then opens the browser
6. Ctrl+C stops both servers together (no orphans)

If `web/node_modules` is missing you will be asked to run `npm install`.

## Test users

```powershell
python -m src.local.create_test_user   # Email/Password prompts (hidden)
python -m src.local.create_test_admin  # admin role
python -m src.local.seed               # one quick demo user (explicit only)
```

Login → Dashboard → Weekly View (pick 1–2 themes) → Portfolio → Performance →
Ranking → Account → Logout all work. `LOCAL` (or `LOCAL REPLAY` after
`python -m src.local.replay`) badge is always visible.

## Other commands

```powershell
python -m src.local.reset              # delete LOCAL DB only (confirmation)
python -m src.local.replay --start 2026-06-01 --days 30  # optional demo replay
scripts/local_smoke_test.py            # health + live-DB-untouched check
```

## Troubleshooting

- PowerShell `ExecutionPolicy` blocks `.ps1`: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`
- Port 3000/8000 busy: close the other dev server (`taskkill /IM node.exe` / `python.exe`)
- Port 3000 shows blank: wait ~30s for Next.js first compile, then refresh
