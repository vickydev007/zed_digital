from __future__ import annotations
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.models.tenant import User, Tenant
from backend.schemas.passage import PassageEventResponse, PresenceSessionResponse
from backend.services.passage_service import (
    list_passage_events,
    get_passage_event_by_id,
    review_passage_event,
    list_presence_sessions
)
from backend.api.deps import get_current_user, get_current_tenant, require_operator

router = APIRouter(prefix='/passage', tags=['Passage & Presence'])

@router.get('/events', response_model=List[PassageEventResponse])
def get_passage_events(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    identity_status: Optional[str] = None,
    passage_status: Optional[str] = None,
    display_category: Optional[str] = None,
    worker_id: Optional[str] = None,
    camera_id: Optional[str] = None,
    video_job_id: Optional[str] = None,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    events, _ = list_passage_events(
        db=db,
        tenant_id=current_tenant.id,
        skip=skip,
        limit=limit,
        identity_status=identity_status,
        passage_status=passage_status,
        display_category=display_category,
        worker_id=worker_id,
        camera_id=camera_id,
        video_job_id=video_job_id
    )
    return [PassageEventResponse.model_validate(e) for e in events]

@router.get('/events/{event_id}', response_model=PassageEventResponse)
def get_event_detail(
    event_id: str,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    event = get_passage_event_by_id(db, current_tenant.id, event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Passage event '{event_id}' not found in this tenant"
        )
    return PassageEventResponse.model_validate(event)

@router.post('/events/{event_id}/review', response_model=PassageEventResponse)
def review_event(
    event_id: str,
    is_reviewed: bool = Query(True),
    current_tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    _auth: bool = Depends(require_operator),
    db: Session = Depends(get_db)
):
    try:
        event = review_passage_event(
            db=db,
            tenant_id=current_tenant.id,
            event_id=event_id,
            is_reviewed=is_reviewed,
            user_id=current_user.id
        )
        return PassageEventResponse.model_validate(event)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

@router.get('/presence', response_model=List[PresenceSessionResponse])
def get_presence_sessions(
    is_present: Optional[bool] = None,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    sessions = list_presence_sessions(db, current_tenant.id, is_currently_present=is_present)
    return [PresenceSessionResponse.model_validate(s) for s in sessions]
