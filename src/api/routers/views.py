"""View routes (owner-scoped; state-changing calls need CSRF)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ..authz import enforce_owner, get_current_user, require_csrf
from ..dependencies import get_db
from ..schemas.view import ViewSubmit
from ..services import view_service as svc

router = APIRouter(prefix="/participants/{participant_id}/views", tags=["views"])


@router.get("", summary="View history for a participant")
def list_views(participant_id: str, status: str | None = Query(default=None),
               limit: int = Query(default=50, ge=1, le=200),
               offset: int = Query(default=0, ge=0), db=Depends(get_db),
               user=Depends(get_current_user)):
    enforce_owner(user, participant_id)
    items, total = svc.list_views(db, participant_id, status, limit, offset)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/current", summary="Currently active views (max 2)")
def current_views(participant_id: str, db=Depends(get_db),
                  user=Depends(get_current_user)):
    enforce_owner(user, participant_id)
    items = svc.current(db, participant_id)
    return {"items": items, "total": len(items)}


@router.post("", status_code=201, summary="Submit weekly view(s)")
def submit_views(participant_id: str, body: ViewSubmit, db=Depends(get_db),
                 user=Depends(require_csrf)):
    enforce_owner(user, participant_id)
    items = svc.submit(db, participant_id, body.theme_ids, body.reason)
    return {"views": items}


@router.post("/{view_id}/close", summary="Close a view")
def close_view(participant_id: str, view_id: str, db=Depends(get_db),
               user=Depends(require_csrf)):
    enforce_owner(user, participant_id)
    return svc.close(db, participant_id, view_id)
