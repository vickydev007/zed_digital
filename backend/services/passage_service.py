from __future__ import annotations
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from backend.models.passage import PassageEvent, PresenceSession
from backend.services.audit_service import log_audit_event

def list_passage_events(
    db: Session,
    tenant_id: str,
    skip: int = 0,
    limit: int = 50,
    identity_status: Optional[str] = None,
    passage_status: Optional[str] = None,
    display_category: Optional[str] = None,
    worker_id: Optional[str] = None,
    camera_id: Optional[str] = None,
    video_job_id: Optional[str] = None
) -> Tuple[List[PassageEvent], int]:
    stmt = select(PassageEvent).where(PassageEvent.tenant_id == tenant_id)
    if identity_status:
        stmt = stmt.where(PassageEvent.identity_status == identity_status.upper())
    if passage_status:
        stmt = stmt.where(PassageEvent.passage_status == passage_status.upper())
    if display_category:
        stmt = stmt.where(PassageEvent.display_category == display_category.upper())
    if worker_id:
        stmt = stmt.where(PassageEvent.worker_id == worker_id)
    if camera_id:
        stmt = stmt.where(PassageEvent.camera_id == camera_id)
    if video_job_id:
        stmt = stmt.where(PassageEvent.video_job_id == video_job_id)

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    events = list(db.execute(stmt.offset(skip).limit(limit).order_by(PassageEvent.event_timestamp.desc())).scalars().all())
    return events, total

def get_passage_event_by_id(db: Session, tenant_id: str, event_id: str) -> Optional[PassageEvent]:
    stmt = select(PassageEvent).where(PassageEvent.tenant_id == tenant_id, PassageEvent.id == event_id)
    return db.execute(stmt).scalar_one_or_none()

def review_passage_event(db: Session, tenant_id: str, event_id: str, is_reviewed: bool = True, user_id: Optional[str] = None) -> PassageEvent:
    event = get_passage_event_by_id(db, tenant_id, event_id)
    if not event:
        raise ValueError(f"Passage event '{event_id}' not found.")
    
    event.is_reviewed = is_reviewed
    db.commit()
    db.refresh(event)
    
    log_audit_event(
        db=db,
        action='REVIEW_PASSAGE_EVENT',
        entity_type='PASSAGE_EVENT',
        entity_id=event.id,
        tenant_id=tenant_id,
        user_id=user_id,
        details={'is_reviewed': is_reviewed}
    )
    return event

def list_presence_sessions(
    db: Session,
    tenant_id: str,
    is_currently_present: Optional[bool] = None
) -> List[PresenceSession]:
    stmt = select(PresenceSession).where(PresenceSession.tenant_id == tenant_id)
    if is_currently_present is not None:
        stmt = stmt.where(PresenceSession.is_currently_present == is_currently_present)
    return list(db.execute(stmt.order_by(PresenceSession.session_start.desc())).scalars().all())
