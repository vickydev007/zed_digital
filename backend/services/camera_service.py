from __future__ import annotations
from typing import Optional, List, Tuple
from datetime import datetime, timezone
from urllib.parse import urlparse
import ipaddress
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from backend.models.camera import Camera, CameraCredential
from backend.schemas.camera import CameraCreateRequest, CameraUpdateRequest
from backend.core.security import encrypt_secret, decrypt_secret
from backend.services.audit_service import log_audit_event

def validate_stream_url(url: str) -> str:
    cleaned = url.strip()
    parsed = urlparse(cleaned)
    if parsed.scheme.lower() not in ('rtsp', 'rtsps', 'http', 'https'):
        raise ValueError(f"Unsupported stream scheme '{parsed.scheme}'. Must be rtsp, rtsps, http, or https.")
    hostname = parsed.hostname
    if not hostname:
        raise ValueError('Missing hostname in stream URL.')
    lower_host = hostname.lower()
    if lower_host in ('localhost', '127.0.0.1', '::1', '169.254.169.254', 'metadata.google.internal'):
        raise ValueError('Forbidden stream destination host: loopback or cloud metadata endpoints are rejected.')
    try:
        ip = ipaddress.ip_address(hostname)
        if ip.is_loopback or ip.is_link_local:
            raise ValueError('Forbidden IP destination.')
    except ValueError as exc:
        if 'Forbidden' in str(exc):
            raise
    return cleaned

def list_cameras(
    db: Session,
    tenant_id: str,
    skip: int = 0,
    limit: int = 50,
    is_active: Optional[bool] = None
) -> Tuple[List[Camera], int]:
    stmt = select(Camera).where(Camera.tenant_id == tenant_id)
    if is_active is not None:
        stmt = stmt.where(Camera.is_active == is_active)
    
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    cameras = list(db.execute(stmt.offset(skip).limit(limit).order_by(Camera.created_at.desc())).scalars().all())
    return cameras, total

def get_camera_by_id(db: Session, tenant_id: str, camera_id: str) -> Optional[Camera]:
    stmt = select(Camera).where(Camera.tenant_id == tenant_id, Camera.id == camera_id)
    return db.execute(stmt).scalar_one_or_none()

def create_camera(db: Session, tenant_id: str, data: CameraCreateRequest, user_id: Optional[str] = None) -> Camera:
    encrypted_url = None
    if data.rtsp_url:
        validated_url = validate_stream_url(data.rtsp_url)
        encrypted_url = encrypt_secret(validated_url)
    
    camera = Camera(
        tenant_id=tenant_id,
        name=data.name.strip(),
        location=data.location.strip() if data.location else None,
        rtsp_url_encrypted=encrypted_url,
        is_active=True,
        status='OFFLINE',
        stream_fps=data.stream_fps
    )
    db.add(camera)
    db.commit()
    db.refresh(camera)
    
    log_audit_event(
        db=db,
        action='CREATE_CAMERA',
        entity_type='CAMERA',
        entity_id=camera.id,
        tenant_id=tenant_id,
        user_id=user_id,
        details={'name': camera.name, 'location': camera.location}
    )
    return camera

def update_camera(db: Session, tenant_id: str, camera_id: str, data: CameraUpdateRequest, user_id: Optional[str] = None) -> Camera:
    camera = get_camera_by_id(db, tenant_id, camera_id)
    if not camera:
        raise ValueError(f"Camera '{camera_id}' not found.")
    
    if data.name is not None:
        camera.name = data.name.strip()
    if data.location is not None:
        camera.location = data.location.strip()
    if data.stream_fps is not None:
        camera.stream_fps = data.stream_fps
    if data.is_active is not None:
        camera.is_active = data.is_active
    if data.rtsp_url is not None:
        if data.rtsp_url:
            validated_url = validate_stream_url(data.rtsp_url)
            camera.rtsp_url_encrypted = encrypt_secret(validated_url)
        else:
            camera.rtsp_url_encrypted = None
    
    db.commit()
    db.refresh(camera)
    
    log_audit_event(
        db=db,
        action='UPDATE_CAMERA',
        entity_type='CAMERA',
        entity_id=camera.id,
        tenant_id=tenant_id,
        user_id=user_id,
        details={'name': camera.name, 'status': camera.status}
    )
    return camera

def delete_camera(db: Session, tenant_id: str, camera_id: str, user_id: Optional[str] = None) -> bool:
    camera = get_camera_by_id(db, tenant_id, camera_id)
    if not camera:
        return False
    
    db.delete(camera)
    db.commit()
    
    log_audit_event(
        db=db,
        action='DELETE_CAMERA',
        entity_type='CAMERA',
        entity_id=camera_id,
        tenant_id=tenant_id,
        user_id=user_id
    )
    return True

def set_camera_status(db: Session, tenant_id: str, camera_id: str, status: str, user_id: Optional[str] = None) -> Camera:
    camera = get_camera_by_id(db, tenant_id, camera_id)
    if not camera:
        raise ValueError(f"Camera '{camera_id}' not found.")
    
    camera.status = status
    if status == 'ONLINE':
        camera.last_heartbeat = datetime.now(timezone.utc)
    db.commit()
    db.refresh(camera)
    
    log_audit_event(
        db=db,
        action=f'CAMERA_{status}',
        entity_type='CAMERA',
        entity_id=camera.id,
        tenant_id=tenant_id,
        user_id=user_id
    )
    return camera
