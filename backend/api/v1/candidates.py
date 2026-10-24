from __future__ import annotations
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.models.tenant import User, Tenant
from backend.schemas.candidate import CandidateResponse, CandidateReviewRequest
from backend.services.candidate_service import (
    list_candidates,
    get_candidate_by_id,
    review_candidate
)
from backend.api.deps import get_current_user, get_current_tenant, require_operator

router = APIRouter(prefix='/candidates', tags=['Candidate Identities'])

@router.get('', response_model=List[CandidateResponse])
def get_candidates(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    review_status: Optional[str] = None,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    candidates, _ = list_candidates(
        db=db,
        tenant_id=current_tenant.id,
        skip=skip,
        limit=limit,
        review_status=review_status
    )
    return [CandidateResponse.model_validate(c) for c in candidates]

@router.get('/{candidate_id}', response_model=CandidateResponse)
def get_candidate(
    candidate_id: str,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    candidate = get_candidate_by_id(db, current_tenant.id, candidate_id)
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidate '{candidate_id}' not found in this tenant"
        )
    return CandidateResponse.model_validate(candidate)

@router.post('/{candidate_id}/review', response_model=CandidateResponse)
def review_candidate_identity(
    candidate_id: str,
    data: CandidateReviewRequest,
    current_tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    _auth: bool = Depends(require_operator),
    db: Session = Depends(get_db)
):
    try:
        candidate = review_candidate(
            db=db,
            tenant_id=current_tenant.id,
            candidate_id=candidate_id,
            data=data,
            user_id=current_user.id
        )
        return CandidateResponse.model_validate(candidate)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
