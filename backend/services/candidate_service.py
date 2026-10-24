from __future__ import annotations
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from backend.models.candidate import CandidateIdentity
from backend.models.worker import Worker
from backend.schemas.candidate import CandidateReviewRequest
from backend.services.audit_service import log_audit_event

def list_candidates(
    db: Session,
    tenant_id: str,
    skip: int = 0,
    limit: int = 50,
    review_status: Optional[str] = None
) -> Tuple[List[CandidateIdentity], int]:
    stmt = select(CandidateIdentity).where(CandidateIdentity.tenant_id == tenant_id)
    if review_status:
        stmt = stmt.where(CandidateIdentity.review_status == review_status.upper())
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    candidates = list(db.execute(stmt.offset(skip).limit(limit).order_by(CandidateIdentity.last_seen_at.desc())).scalars().all())
    return candidates, total

def get_candidate_by_id(db: Session, tenant_id: str, candidate_id: str) -> Optional[CandidateIdentity]:
    stmt = select(CandidateIdentity).where(CandidateIdentity.tenant_id == tenant_id, CandidateIdentity.id == candidate_id)
    return db.execute(stmt).scalar_one_or_none()

def review_candidate(
    db: Session,
    tenant_id: str,
    candidate_id: str,
    data: CandidateReviewRequest,
    user_id: Optional[str] = None
) -> CandidateIdentity:
    cand = get_candidate_by_id(db, tenant_id, candidate_id)
    if not cand:
        raise ValueError(f"Candidate '{candidate_id}' not found.")
    
    cand.review_status = data.review_status.upper()
    if data.notes:
        cand.notes = data.notes.strip()
    
    if data.approved_worker_id:
        w_stmt = select(Worker).where(Worker.tenant_id == tenant_id, Worker.id == data.approved_worker_id)
        worker = db.execute(w_stmt).scalar_one_or_none()
        if not worker:
            raise ValueError(f"Worker '{data.approved_worker_id}' not found in this tenant.")
        cand.approved_worker_id = worker.id
    
    db.commit()
    db.refresh(cand)
    
    log_audit_event(
        db=db,
        action='REVIEW_CANDIDATE',
        entity_type='CANDIDATE_IDENTITY',
        entity_id=cand.id,
        tenant_id=tenant_id,
        user_id=user_id,
        details={'review_status': cand.review_status, 'approved_worker_id': cand.approved_worker_id}
    )
    return cand
