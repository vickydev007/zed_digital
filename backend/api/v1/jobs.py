from __future__ import annotations
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.models.tenant import User, Tenant
from backend.schemas.job import JobResponse, JobProgressResponse
from backend.services.video_service import (
    get_job_by_id,
    list_jobs,
    cancel_job
)
from backend.api.deps import get_current_user, get_current_tenant, require_operator

router = APIRouter(prefix='/jobs', tags=['Jobs'])

@router.get('', response_model=List[JobResponse])
def get_jobs(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    status: Optional[str] = None,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    jobs, _ = list_jobs(db, current_tenant.id, skip=skip, limit=limit, status=status)
    return [JobResponse.model_validate(j) for j in jobs]

@router.get('/{job_id}', response_model=JobResponse)
def get_job_details(
    job_id: str,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    job = get_job_by_id(db, current_tenant.id, job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' not found in this tenant"
        )
    return JobResponse.model_validate(job)

@router.get('/{job_id}/progress', response_model=JobProgressResponse)
def get_job_progress(
    job_id: str,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    job = get_job_by_id(db, current_tenant.id, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Job not found')
    return JobProgressResponse(
        id=job.id,
        status=job.status,
        progress_percent=job.progress_percent,
        completed_at=job.completed_at,
        error_details=job.error_details
    )

@router.post('/{job_id}/cancel', response_model=JobResponse)
def cancel_processing_job(
    job_id: str,
    current_tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    _auth: bool = Depends(require_operator),
    db: Session = Depends(get_db)
):
    try:
        job = cancel_job(db, current_tenant.id, job_id, user_id=current_user.id)
        return JobResponse.model_validate(job)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
