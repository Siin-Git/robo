"""Robo Advisor API v1.

WARNING: Phase 3B API does not provide authentication or authorization.
Do not expose this API publicly. Authentication arrives in Phase 3C.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import FastAPI, Request  # noqa: E402
from fastapi.exceptions import RequestValidationError  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from starlette.exceptions import HTTPException as StarletteHTTPException  # noqa: E402
from contextlib import asynccontextmanager  # noqa: E402

from src.api.dependencies import get_db  # noqa: E402,F401
from src.api.errors import ApiError  # noqa: E402
from src.api.middleware.error_handler import (  # noqa: E402
    api_error_handler,
    http_error_handler,
    unhandled_error_handler,
    validation_error_handler,
)
from src.api.middleware.request_id import RequestContextMiddleware  # noqa: E402
from src.api.middleware.capstone_queue import CapstoneRequestQueue  # noqa: E402
from src.api.routers import (  # noqa: E402
    admin,
    auth,
    benchmarks,
    frontier,
    me,
    onboarding,
    participants,
    performance,
    portfolios,
    system,
    themes,
    views,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    from src.db.config import get_backend
    from src.forward.runtime import get_database_path, get_runtime_profile
    print(f"PROFILE: {get_runtime_profile().upper()}", flush=True)
    print(f"DATABASE_BACKEND: {get_backend().upper()}", flush=True)
    try:
        from src.local.capstone import enabled
        print(f"DATABASE: {'data/capstone_demo.db' if enabled() else get_database_path().relative_to(ROOT)}", flush=True)
    except ValueError:
        print(f"DATABASE: {get_database_path()}", flush=True)
    print("API VERSION: v1", flush=True)
    yield


app = FastAPI(title="Robo Advisor API", version="0.1.0",
              description="Paper-trading forward-test API (no auth in Phase 3B).",
              lifespan=lifespan)

ALLOWED = [o.strip() for o in os.environ.get(
    "CORS_ALLOWED_ORIGINS", "http://localhost:3000").split(",") if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=ALLOWED, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])
app.add_middleware(RequestContextMiddleware)
app.add_middleware(CapstoneRequestQueue)
app.add_exception_handler(ApiError, api_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(StarletteHTTPException, http_error_handler)
app.add_exception_handler(Exception, unhandled_error_handler)


@app.get("/health", summary="Liveness probe")
def health():
    return {"status": "ok"}


@app.get("/ready", summary="Readiness probe (DB + benchmark + themes)")
def ready():
    from sqlalchemy import select
    from src.api.dependencies import get_session_factory
    from src.api.services import _common as C
    from src.db.models.operational import ForwardState
    from src.db.models.price import PriceDaily as _Px
    from src.db.models.theme import Theme as _T
    factory = get_session_factory()
    try:
        with factory() as db:
            px = db.scalars(select(_Px.date).order_by(_Px.date.desc())).first()
            themes = db.scalars(select(_T).where(_T.active.is_(True))).all()
            frozen_w, _ = C.frozen_bundle()
            inception = db.get(ForwardState, "forward_test_inception_at")
    except Exception as e:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=503, content={
            "status": "not_ready", "reason": str(e)})
    from src.forward.state import get_state as _gs
    from src.api.services import market_comparison
    if market_comparison.enabled():
        px = market_comparison.price_date()
    problems = []
    if px is None:
        problems.append("no market data")
    if not themes:
        problems.append("no active themes")
    if not frozen_w:
        problems.append("benchmark unavailable")
    if problems:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=503, content={
            "status": "not_ready", "reasons": problems})
    return {"status": "ready", "database": "ok", "benchmark": "CORE_V0.3",
            "theme_universe": "THEME_UNIVERSE_V0.1",
            "forward_test_status": "started" if inception and inception.value else "not_started"}


app.include_router(auth.router, prefix="/api/v1")
app.include_router(me.router, prefix="/api/v1")
app.include_router(onboarding.router, prefix="/api/v1")
app.include_router(frontier.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(participants.router, prefix="/api/v1")
app.include_router(themes.router, prefix="/api/v1")
app.include_router(views.router, prefix="/api/v1")
app.include_router(portfolios.router, prefix="/api/v1")
app.include_router(performance.router, prefix="/api/v1")
app.include_router(benchmarks.router, prefix="/api/v1")
app.include_router(system.router, prefix="/api/v1")

from src.api.routers import enrollment
app.include_router(enrollment.router, prefix="/api/v1")

from .routers import decisions
app.include_router(decisions.router, prefix="/api/v1")
