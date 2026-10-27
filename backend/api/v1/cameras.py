from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query, Header, Request, Body
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.core.database import get_db
from backend.core.security import decode_access_token, create_access_token
from backend.models.tenant import User, Tenant, TenantMembership
from backend.models.camera import Camera
from backend.schemas.camera import (
    CameraCreateRequest,
    CameraUpdateRequest,
    CameraResponse,
    CameraActionResponse,
    CameraRuntimeStatusResponse,
    CameraTestConnectionRequest,
    CameraTestConnectionResponse,
    CameraPreviewTokenResponse,
    ClientLatencyReportRequest
)
from backend.services.camera_service import (
    list_cameras,
    get_camera_by_id,
    create_camera,
    update_camera,
    delete_camera,
    set_camera_status
)
from backend.services.camera_streamer import stream_manager
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

@router.post('/test-connection', response_model=CameraTestConnectionResponse)
def test_camera_connection(
    data: CameraTestConnectionRequest,
    current_tenant: Tenant = Depends(get_current_tenant),
    _auth: bool = Depends(require_operator)
):
    res = stream_manager.test_connectivity(data.rtsp_url)
    return CameraTestConnectionResponse(**res)

@router.post('/{camera_id}/start', response_model=CameraActionResponse)
def start_camera_feed(
    camera_id: str,
    current_tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    _auth: bool = Depends(require_operator),
    db: Session = Depends(get_db)
):
    camera = get_camera_by_id(db, current_tenant.id, camera_id)
    if not camera:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Camera '{camera_id}' not found in this tenant")
    try:
        worker = stream_manager.start_camera_stream(
            tenant_id=current_tenant.id,
            camera_id=camera_id,
            user_id=current_user.id,
            db=db
        )
        set_camera_status(db, current_tenant.id, camera_id, worker.status, user_id=current_user.id)
        return CameraActionResponse(id=camera.id, name=camera.name, status='ONLINE', action_performed='STARTED')
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Stream start error: {str(exc)}")

@router.post('/{camera_id}/stop', response_model=CameraActionResponse)
def stop_camera_feed(
    camera_id: str,
    current_tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    _auth: bool = Depends(require_operator),
    db: Session = Depends(get_db)
):
    camera = get_camera_by_id(db, current_tenant.id, camera_id)
    if not camera:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Camera '{camera_id}' not found in this tenant")
    stream_manager.stop_camera_stream(camera_id, user_id=current_user.id, db=db)
    set_camera_status(db, current_tenant.id, camera_id, 'OFFLINE', user_id=current_user.id)
    return CameraActionResponse(id=camera.id, name=camera.name, status='OFFLINE', action_performed='STOPPED')


@router.get('/{camera_id}/status', response_model=CameraRuntimeStatusResponse)
def get_camera_runtime_status(
    camera_id: str,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    camera = get_camera_by_id(db, current_tenant.id, camera_id)
    if not camera:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Camera '{camera_id}' not found in this tenant")
    
    status_dict = stream_manager.get_status(camera_id)
    if not status_dict:
        status_dict = {
            'camera_id': camera.id,
            'tenant_id': camera.tenant_id,
            'status': camera.status,
            'received_fps': 0.0,
            'processed_fps': 0.0,
            'received_frames': 0,
            'processed_frames': 0,
            'active_tracks': 0,
            'reconnect_count': 0,
            'last_frame_time': camera.last_heartbeat.isoformat() if camera.last_heartbeat else None,
            'last_error': None,
            'uptime_seconds': 0.0,
            'consumer_count': 0,
            'sanitized_url': None,
            'policy_id': getattr(settings, 'ACTIVE_POLICY_ID', 'POL-ALERTING-V1'),
            'operating_tau': float(getattr(settings, 'DEFAULT_SCORE_THRESHOLD', 0.85)),
            'operating_margin': float(getattr(settings, 'DEFAULT_CONTRAST_MARGIN', 0.10)),
            'camera_profile': 'C5_PHOTOMETRIC' if 'c5' in camera.name.lower() or 'c5' in camera.id.lower() else 'DEFAULT'
        }
    return CameraRuntimeStatusResponse(**status_dict)

@router.post('/{camera_id}/preview-token', response_model=CameraPreviewTokenResponse)
def generate_camera_preview_token(
    camera_id: str,
    current_tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    camera = get_camera_by_id(db, current_tenant.id, camera_id)
    if not camera:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Camera '{camera_id}' not found in authorized tenant")

    from datetime import timedelta
    preview_claims = {
        "sub": current_user.id,
        "scope": "camera_preview",
        "camera_id": camera_id,
        "tenant_id": current_tenant.id
    }
    preview_token = create_access_token(preview_claims, expires_delta=timedelta(seconds=120))
    return CameraPreviewTokenResponse(
        preview_token=preview_token,
        expires_in_seconds=120,
        camera_id=camera_id,
        tenant_id=current_tenant.id
    )

_revoked_preview_tokens: set[str] = set()

@router.post('/{camera_id}/revoke-token')
def revoke_camera_preview_token(
    camera_id: str,
    payload: Dict[str, Any] = Body(...),
    current_tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
):
    token_to_revoke = payload.get("token")
    if token_to_revoke and isinstance(token_to_revoke, str):
        _revoked_preview_tokens.add(token_to_revoke.strip())
        if len(_revoked_preview_tokens) > 5000:
            _revoked_preview_tokens.clear()
    return {"status": "REVOKED", "camera_id": camera_id}

def is_preview_token_revoked(token: str) -> bool:
    return token in _revoked_preview_tokens

@router.get('/{camera_id}/preview')
def get_camera_preview_stream(
    camera_id: str,
    request: Request,
    token: Optional[str] = Query(None),
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID"),
    db: Session = Depends(get_db)
):
    auth_header = request.headers.get("Authorization")
    raw_token = None
    if auth_header and auth_header.startswith("Bearer "):
        raw_token = auth_header[7:].strip()
    elif token:
        raw_token = token.strip()
    elif request.cookies.get("reid_preview_token"):
        raw_token = request.cookies.get("reid_preview_token").strip()
    elif request.cookies.get("reid_auth_token"):
        raw_token = request.cookies.get("reid_auth_token").strip()

    if not raw_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing authentication token")

    if is_preview_token_revoked(raw_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Preview token has been revoked")

    payload = decode_access_token(raw_token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user_id = payload.get("sub")
    user = db.execute(select(User).where(User.id == user_id, User.is_active == True)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    if payload.get("scope") == "camera_preview":
        token_cam_id = payload.get("camera_id")
        token_tnt_id = payload.get("tenant_id")
        if token_cam_id != camera_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Preview token not authorized for this camera ID")
        target_tenant_id = token_tnt_id
    else:
        target_tenant_id = x_tenant_id or request.query_params.get("tenant_id")
        if target_tenant_id:
            if not user.is_superuser:
                mem = db.execute(select(TenantMembership).where(TenantMembership.user_id == user.id, TenantMembership.tenant_id == target_tenant_id)).scalar_one_or_none()
                if not mem:
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant access forbidden.")
        else:
            mem = db.execute(select(TenantMembership).where(TenantMembership.user_id == user.id)).scalar_one_or_none()
            if not mem and not user.is_superuser:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tenant membership.")
            target_tenant_id = mem.tenant_id if mem else None

    camera = db.execute(select(Camera).where(Camera.id == camera_id)).scalar_one_or_none()
    if not camera or (target_tenant_id and camera.tenant_id != target_tenant_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera not found in authorized tenant")

    worker = stream_manager.get_worker(camera_id)
    if not worker or worker.status == 'OFFLINE':
        try:
            worker = stream_manager.start_camera_stream(
                tenant_id=camera.tenant_id,
                camera_id=camera.id,
                user_id=user.id,
                db=db
            )
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Cannot stream preview: {str(exc)}")

    return StreamingResponse(
        worker.generate_mjpeg_stream(is_revoked_fn=lambda: is_preview_token_revoked(raw_token)),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

@router.get('/{camera_id}/latency')
def get_camera_latency_metrics(
    camera_id: str,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    camera = get_camera_by_id(db, current_tenant.id, camera_id)
    if not camera:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Camera '{camera_id}' not found in authorized tenant")

    stats = stream_manager.get_latency(camera_id)
    if not stats:
        return {
            "camera_id": camera_id,
            "status": "INACTIVE",
            "message": "Stream worker not active; latency telemetry unavailable."
        }
    return stats

@router.post('/{camera_id}/client-latency')
def report_client_browser_latency(
    camera_id: str,
    payload: ClientLatencyReportRequest,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    camera = get_camera_by_id(db, current_tenant.id, camera_id)
    if not camera:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Camera '{camera_id}' not found in authorized tenant")

    recorded = stream_manager.record_client_latency(
        camera_id=camera_id,
        frame_idx=payload.frame_idx,
        capture_timestamp=payload.capture_timestamp,
        display_timestamp=payload.display_timestamp,
        display_latency_ms=payload.display_latency_ms
    )
    return {"success": recorded, "camera_id": camera_id}

