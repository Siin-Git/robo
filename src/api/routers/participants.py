"""Participant routes (admin-managed since Phase 3C)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ..authz import enforce_owner, get_current_user, require_admin
from ..dependencies import get_db
from ..schemas.participant import ParticipantCreate, ParticipantOut
from ..services import participant_service as svc

router = APIRouter(prefix="/participants", tags=["participants"])


@router.get("", summary="List participants (admin)")
def list_participants(status: str | None = Query(default=None),
                      limit: int = Query(default=50, ge=1, le=200),
                      offset: int = Query(default=0, ge=0),
                      db=Depends(get_db), admin=Depends(require_admin)):
    items, total = svc.list(db, status, limit, offset)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.post("", status_code=201, summary="Register participant (admin)")
def create_participant(body: ParticipantCreate, db=Depends(get_db),
                       admin=Depends(require_admin)):
    return svc.create(db, body.display_name)


@router.get("/{participant_id}", response_model=ParticipantOut, summary="Participant detail")
def get_participant(participant_id: str, db=Depends(get_db),
                    user=Depends(get_current_user)):
    enforce_owner(user, participant_id)
    return svc.get(db, participant_id)


@router.post("/{participant_id}/deactivate", summary="Deactivate participant (admin)")
def deactivate_participant(participant_id: str, db=Depends(get_db),
                           admin=Depends(require_admin)):
    return svc.set_status(db, participant_id, False)


@router.post("/{participant_id}/reactivate", summary="Reactivate participant (admin)")
def reactivate_participant(participant_id: str, db=Depends(get_db),
                           admin=Depends(require_admin)):
    return svc.set_status(db, participant_id, True)
