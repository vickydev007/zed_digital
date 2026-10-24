from __future__ import annotations
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.models.tenant import User, Tenant
from backend.models.worker import Worker
from backend.schemas.worker import (
    WorkerCreateRequest,
    WorkerUpdateRequest,
    WorkerResponse,
    WorkerEnrollResponse
)
from backend.services.worker_service import (
    list_workers,
    get_worker_by_id,
    create_worker,
    update_worker,
    deactivate_worker,
    enroll_worker_image
)
from backend.api.deps import get_current_user, get_current_tenant, require_operator, require_admin

router = APIRouter(prefix='/workers', tags=['Workers'])

@router.get('', response_model=List[WorkerResponse])
def get_workers(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    search: Optional[str] = None,
    department: Optional[str] = None,
    is_active: Optional[bool] = None,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    workers, _ = list_workers(
        db=db,
        tenant_id=current_tenant.id,
        skip=skip,
        limit=limit,
        search=search,
        department=department,
        is_active=is_active
    )
    return [WorkerResponse.model_validate(w) for w in workers]

@router.post('', response_model=WorkerResponse, status_code=status.HTTP_201_CREATED)
def create_new_worker(
    data: WorkerCreateRequest,
    current_tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    _auth: bool = Depends(require_operator),
    db: Session = Depends(get_db)
):
    try:
        worker = create_worker(db, current_tenant.id, data, user_id=current_user.id)
        return WorkerResponse.model_validate(worker)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

@router.get('/{worker_id}', response_model=WorkerResponse)
def get_worker(
    worker_id: str,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    worker = get_worker_by_id(db, current_tenant.id, worker_id)
    if not worker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Worker '{worker_id}' not found in tenant '{current_tenant.id}'"
        )
    return WorkerResponse.model_validate(worker)

@router.patch('/{worker_id}', response_model=WorkerResponse)
def update_worker_info(
    worker_id: str,
    data: WorkerUpdateRequest,
    current_tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    _auth: bool = Depends(require_operator),
    db: Session = Depends(get_db)
):
    try:
        worker = update_worker(db, current_tenant.id, worker_id, data, user_id=current_user.id)
        return WorkerResponse.model_validate(worker)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

@router.post('/{worker_id}/deactivate', response_model=WorkerResponse)
def deactivate_worker_account(
    worker_id: str,
    current_tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    _auth: bool = Depends(require_admin),
    db: Session = Depends(get_db)
):
    try:
        worker = deactivate_worker(db, current_tenant.id, worker_id, user_id=current_user.id)
        return WorkerResponse.model_validate(worker)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

@router.post('/{worker_id}/enroll', response_model=WorkerEnrollResponse)
async def enroll_worker_photo(
    worker_id: str,
    file: UploadFile = File(...),
    is_primary: bool = Query(True),
    current_tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    _auth: bool = Depends(require_operator),
    db: Session = Depends(get_db)
):
    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Empty image file provided')
    try:
        res = enroll_worker_image(
            db=db,
            tenant_id=current_tenant.id,
            worker_id=worker_id,
            image_bytes=content,
            is_primary=is_primary,
            user_id=current_user.id
        )
        return WorkerEnrollResponse(**res)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
