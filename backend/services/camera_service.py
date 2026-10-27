from __future__ import annotations
from typing import Optional, List, Tuple
from datetime import datetime, timezone
from urllib.parse import urlparse
import ipaddress
import socket
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from backend.models.camera import Camera, CameraCredential
from backend.schemas.camera import CameraCreateRequest, CameraUpdateRequest
from backend.core.security import encrypt_secret, decrypt_secret
from backend.core.config import settings
from backend.services.audit_service import log_audit_event

def _parse_flexible_ip(hostname: str) -> Optional[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    if not hostname:
        return None
    try:
        return ipaddress.ip_address(hostname)
    except ValueError:
        pass

    s = hostname.strip().lower()
    try:
        if s.startswith(('0x', '0o')):
            val = int(s, 0)
        elif len(s) > 1 and s.startswith('0') and s.isdigit():
            val = int(s, 8)
        elif s.isdigit():
            val = int(s, 10)
        else:
            val = None
        if val is not None and 0 <= val <= 0xFFFFFFFF:
            return ipaddress.IPv4Address(val)
    except (ValueError, OverflowError):
        pass

    parts = s.split('.')
    if len(parts) == 4:
        try:
            byte_vals = []
            for p in parts:
                if p.startswith(('0x', '0o')):
                    p_val = int(p, 0)
                elif len(p) > 1 and p.startswith('0') and p.isdigit():
                    p_val = int(p, 8)
                elif p.isdigit():
                    p_val = int(p, 10)
                else:
                    return None
                if not (0 <= p_val <= 255):
                    return None
                byte_vals.append(p_val)
            return ipaddress.IPv4Address(bytes(byte_vals))
        except (ValueError, OverflowError):
            pass

    return None

def validate_stream_url(url: str) -> str:
    cleaned = url.strip()
    parsed = urlparse(cleaned)
    if parsed.scheme.lower() not in ('rtsp', 'rtsps', 'http', 'https'):
        raise ValueError(f"Unsupported stream scheme '{parsed.scheme}'. Must be rtsp, rtsps, http, or https.")
    hostname = parsed.hostname
    if not hostname:
        raise ValueError('Missing hostname in stream URL.')
    lower_host = hostname.lower()
    if lower_host in ('localhost', '127.0.0.1', '::1', '169.254.169.254', 'metadata.google.internal', 'instance-data'):
        raise ValueError('Forbidden stream destination host: loopback or cloud metadata endpoints are rejected.')

    PROHIBITED_PORTS = {
        21, 22, 23, 25, 53, 67, 68, 69, 110, 111, 123, 135, 137, 138, 139, 445,
        1433, 1521, 2049, 2375, 2376, 2379, 2380, 3306, 3389, 5432, 6379, 6443, 8086,
        9090, 9200, 9300, 10000, 10250, 11211, 27017, 27018
    }
    if parsed.port and parsed.port in PROHIBITED_PORTS:
        raise ValueError(f"Forbidden stream destination port {parsed.port}: sensitive administrative/database ports are blocked.")

    allow_private_1 = getattr(settings, 'ALLOW_PRIVATE_RTSP', True)
    allow_private_2 = getattr(settings, 'ALLOW_PRIVATE_RTSP_NETWORKS', True)
    allow_private = bool(allow_private_1 and allow_private_2)

    allowed_subnets = []
    subnet_cfg = getattr(settings, 'ALLOWED_CAMERA_SUBNETS', '')
    if subnet_cfg and subnet_cfg.strip():
        for sn in subnet_cfg.split(','):
            sn = sn.strip()
            if sn:
                try:
                    allowed_subnets.append(ipaddress.ip_network(sn, strict=False))
                except ValueError:
                    pass

    def _check_ip_safety(ip_obj: ipaddress.IPv4Address | ipaddress.IPv6Address):
        if getattr(ip_obj, 'ipv4_mapped', None):
            _check_ip_safety(ip_obj.ipv4_mapped)
        if ip_obj.is_loopback or ip_obj.is_link_local or ip_obj.is_unspecified or ip_obj.is_multicast or str(ip_obj) == '0.0.0.0':
            raise ValueError('Forbidden IP destination.')
        if str(ip_obj) in ('169.254.169.254', '::ffff:169.254.169.254'):
            raise ValueError('Forbidden stream destination: cloud metadata address is rejected.')
        if not allow_private and ip_obj.is_private:
            raise ValueError('Forbidden IP destination: private network address rejected by policy.')
        if allowed_subnets and ip_obj.is_private:
            if not any(ip_obj in net for net in allowed_subnets):
                raise ValueError('Forbidden IP destination: private address not within ALLOWED_CAMERA_SUBNETS.')

    parsed_ip = _parse_flexible_ip(hostname)
    if parsed_ip is not None:
        _check_ip_safety(parsed_ip)
    else:
        try:
            addr_info = socket.getaddrinfo(hostname, None)
            for item in addr_info:
                resolved_ip_str = item[4][0]
                res_ip = ipaddress.ip_address(resolved_ip_str)
                _check_ip_safety(res_ip)
        except socket.gaierror:
            pass
        except ValueError as v_exc:
            if 'Forbidden' in str(v_exc):
                raise

    return cleaned

def sanitize_stream_url(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    import re
    redacted = re.sub(r'(://[^:]+:)[^@]+@', r'\1***@', url)
    if redacted == url:
        redacted = re.sub(r'(://)[^@/]+@', r'\1***@', url)
    redacted = re.sub(r'([?&](?:token|key|auth|secret|password|pass|pwd)=)[^&]+', r'\1***', redacted, flags=re.IGNORECASE)
    return redacted


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
