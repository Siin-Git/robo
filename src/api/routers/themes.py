"""Theme + benchmark routes (any authenticated login)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ..authz import get_current_user
from ..dependencies import get_db
from ..errors import not_found
from ...db.repositories.forward import ThemeRepository

router = APIRouter(prefix="/themes", tags=["themes"])


def _out(t) -> dict:
    from ..services import _common as C
    return {"theme_id": t.theme_id, "display_name": t.display_name,
            "theme_type": t.theme_type, "ticker": t.ticker, "market": t.market,
            "currency": t.currency, "active": bool(t.active),
            "universe_version": t.universe_version,
            "valid_from": C.as_date(t.valid_from), "valid_to": C.as_date(t.valid_to),
            "inactive_reason": t.inactive_reason}


@router.get("", summary="List themes (active only by default)")
def list_themes(active: bool | None = Query(default=True),
                theme_type: str | None = Query(default=None),
                db=Depends(get_db), user=Depends(get_current_user)):
    rows = ThemeRepository(db).list(active)
    if theme_type:
        rows = [r for r in rows if r.theme_type == theme_type]
    return {"items": [_out(r) for r in rows], "total": len(rows)}


@router.get("/{theme_id}", summary="Theme detail (inactive retrievable)")
def get_theme(theme_id: str, db=Depends(get_db), user=Depends(get_current_user)):
    row = ThemeRepository(db).get(theme_id)
    if row is None:
        raise not_found("THEME_NOT_FOUND", f"Unknown theme {theme_id}.")
    return _out(row)
