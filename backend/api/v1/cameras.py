from __future__ import annotations
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.models.tenant import User, Tenant
from backend.models.camera import Camera
from backend.schemas.camera import (
    CameraCreateRequest,
    CameraUpdateRequest,
    CameraResponse,
    CameraActionResponse
)
from backend.services.camera_service import (
    list_cameras,
    get_camera_by_id,
    create_camera,
    update_camera,
    delete_camera,
    set_camera_status
)
from backend.api.deps import get_current_user, get_current_tenant, require_admin, require_operator

router = APIRouter(prefix='/cameras', tags=['Cameras'])

def serialize_camera(camera: Camera) -> CameraResponse:
    return CameraResponse(
        id=camera.id,
        tenant_id=camera.tenant_id,
        name=camera.name,
        location=camera.location,
        is_active=camera.is_active,
        status=camera.status,
        stream_fps=camera.stream_fps,
        last_heartbeat=camera.last_heartbeat,
        has_encrypted_stream=bool(camera.rtsp_url_encrypted),
        created_at=camera.created_at,
        updated_at=camera.updated_at
    )

@router.get('', response_model=List[CameraResponse])
def get_cameras(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    is_active: Optional[bool] = None,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    cameras, _ = list_cameras(
        db=db,
        tenant_id=current_tenant.id,
        skip=skip,
        limit=limit,
        is_active=is_active
    )
    return [serialize_camera(c) for c in cameras]

@router.post('', response_model=CameraResponse, status_code=status.HTTP_201_CREATED)
def create_new_camera(
    data: CameraCreateRequest,
    current_tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    _auth: bool = Depends(require_admin),
    db: Session = Depends(get_db)
):
    try:
        camera = create_camera(db, current_tenant.id, data, user_id=current_user.id)
        return serialize_camera(camera)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

@router.get('/{camera_id}', response_model=CameraResponse)
def get_camera(
    camera_id: str,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    camera = get_camera_by_id(db, current_tenant.id, camera_id)
    if not camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera '{camera_id}' not found in this tenant"
        )
    return serialize_camera(camera)

@router.patch('/{camera_id}', response_model=CameraResponse)
def update_camera_info(
    camera_id: str,
    data: CameraUpdateRequest,
    current_tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    _auth: bool = Depends(require_admin),
    db: Session = Depends(get_db)
):
    try:
        camera = update_camera(db, current_tenant.id, camera_id, data, user_id=current_user.id)
        return serialize_camera(camera)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

@router.delete('/{camera_id}', status_code=status.HTTP_204_NO_CONTENT)
def remove_camera(
    camera_id: str,
    current_tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    _auth: bool = Depends(require_admin),
    db: Session = Depends(get_db)
):
    deleted = delete_camera(db, current_tenant.id, camera_id, user_id=current_user.id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Camera not found')

@router.post('/{camera_id}/start', response_model=CameraActionResponse)
def start_camera_feed(
    camera_id: str,
    current_tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    _auth: bool = Depends(require_operator),
    db: Session = Depends(get_db)
):
    try:
        camera = set_camera_status(db, current_tenant.id, camera_id, 'ONLINE', user_id=current_user.id)
        return CameraActionResponse(id=camera.id, name=camera.name, status=camera.status, action_performed='STARTED')
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

@router.post('/{camera_id}/stop', response_model=CameraActionResponse)
def stop_camera_feed(
    camera_id: str,
    current_tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    _auth: bool = Depends(require_operator),
    db: Session = Depends(get_db)
):
    try:
        camera = set_camera_status(db, current_tenant.id, camera_id, 'OFFLINE', user_id=current_user.id)
        return CameraActionResponse(id=camera.id, name=camera.name, status=camera.status, action_performed='STOPPED')
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
