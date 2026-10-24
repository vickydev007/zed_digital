from __future__ import annotations
import os
import uuid
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select, func
import cv2

from backend.core.config import settings
from backend.models.video import VideoAsset, VideoJob
from backend.schemas.video import VideoAnalyzeRequest
from backend.services.audit_service import log_audit_event
from backend.services.job_worker import enqueue_job_processing, request_job_cancellation

def save_uploaded_video(
    db: Session,
    tenant_id: str,
    file_bytes: bytes,
    original_filename: str,
    camera_id: Optional[str] = None,
    user_id: Optional[str] = None
) -> VideoAsset:
    file_size = len(file_bytes)
    if file_size < 100:
        raise ValueError('Video file is empty or too small.')
    if file_size > 157286400:
        raise ValueError('Video file exceeds maximum allowed upload size (150 MB).')

    file_ext = os.path.splitext(original_filename)[1].lower()
    allowed_exts = {'.mp4', '.avi', '.mov', '.mkv', '.webm'}
    if file_ext not in allowed_exts:
        raise ValueError(f"Unsupported video format '{file_ext}'. Allowed formats: {allowed_exts}")

    target_dir = os.path.join(settings.UPLOAD_DIR, tenant_id)
    os.makedirs(target_dir, exist_ok=True)
    stored_name = f"{uuid.uuid4()}{file_ext}"
    stored_path = os.path.join(target_dir, stored_name)

    with open(stored_path, 'wb') as f:
        f.write(file_bytes)

    cap = cv2.VideoCapture(stored_path)
    if not cap.isOpened():
        validation_status = 'INVALID'
        duration = 0.0
    else:
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if frame_count <= 0 or w <= 0 or h <= 0:
            validation_status = 'INVALID'
            duration = 0.0
        else:
            validation_status = 'VALIDATED'
            duration = float(frame_count / max(1.0, fps))
        cap.release()
    
    asset = VideoAsset(
        tenant_id=tenant_id,
        camera_id=camera_id,
        original_filename=original_filename,
        stored_path=stored_path,
        mime_type='video/mp4',
        file_size_bytes=file_size,
        duration_seconds=round(duration, 2),
        validation_status=validation_status
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    
    log_audit_event(
        db=db,
        action='UPLOAD_VIDEO',
        entity_type='VIDEO_ASSET',
        entity_id=asset.id,
        tenant_id=tenant_id,
        user_id=user_id,
        details={'filename': original_filename, 'size_bytes': file_size, 'status': validation_status}
    )
    return asset

def get_video_by_id(db: Session, tenant_id: str, video_id: str) -> Optional[VideoAsset]:
    stmt = select(VideoAsset).where(VideoAsset.tenant_id == tenant_id, VideoAsset.id == video_id)
    return db.execute(stmt).scalar_one_or_none()

def list_videos(
    db: Session,
    tenant_id: str,
    skip: int = 0,
    limit: int = 50
) -> Tuple[List[VideoAsset], int]:
    stmt = select(VideoAsset).where(VideoAsset.tenant_id == tenant_id)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    videos = list(db.execute(stmt.offset(skip).limit(limit).order_by(VideoAsset.created_at.desc())).scalars().all())
    return videos, total

def create_analysis_job(
    db: Session,
    tenant_id: str,
    video_asset_id: str,
    options: VideoAnalyzeRequest,
    user_id: Optional[str] = None
) -> VideoJob:
    asset = get_video_by_id(db, tenant_id, video_asset_id)
    if not asset:
        raise ValueError(f"Video asset '{video_asset_id}' not found in this tenant.")
    
    if asset.validation_status != 'VALIDATED':
        raise ValueError(f"Video asset '{video_asset_id}' is not in VALIDATED state (status: {asset.validation_status}).")
    
    job = VideoJob(
        tenant_id=tenant_id,
        video_asset_id=asset.id,
        job_type='OFFLINE_REID',
        status='QUEUED',
        progress_percent=0.0
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    
    opts_dict = options.model_dump()
    enqueue_job_processing(job.id, opts_dict)
    
    log_audit_event(
        db=db,
        action='CREATE_VIDEO_JOB',
        entity_type='VIDEO_JOB',
        entity_id=job.id,
        tenant_id=tenant_id,
        user_id=user_id,
        details={'video_asset_id': asset.id, 'options': opts_dict}
    )
    return job

def get_job_by_id(db: Session, tenant_id: str, job_id: str) -> Optional[VideoJob]:
    stmt = select(VideoJob).where(VideoJob.tenant_id == tenant_id, VideoJob.id == job_id)
    return db.execute(stmt).scalar_one_or_none()

def list_jobs(
    db: Session,
    tenant_id: str,
    skip: int = 0,
    limit: int = 50,
    status: Optional[str] = None
) -> Tuple[List[VideoJob], int]:
    stmt = select(VideoJob).where(VideoJob.tenant_id == tenant_id)
    if status:
        stmt = stmt.where(VideoJob.status == status.upper())
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    jobs = list(db.execute(stmt.offset(skip).limit(limit).order_by(VideoJob.created_at.desc())).scalars().all())
    return jobs, total

def cancel_job(db: Session, tenant_id: str, job_id: str, user_id: Optional[str] = None) -> VideoJob:
    job = get_job_by_id(db, tenant_id, job_id)
    if not job:
        raise ValueError(f"Job '{job_id}' not found.")
    
    if job.status in ('COMPLETED', 'FAILED', 'CANCELLED'):
        return job
    
    request_job_cancellation(job.id)
    job.status = 'CANCELLED'
    db.commit()
    db.refresh(job)
    
    log_audit_event(
        db=db,
        action='CANCEL_VIDEO_JOB',
        entity_type='VIDEO_JOB',
        entity_id=job.id,
        tenant_id=tenant_id,
        user_id=user_id
    )
    return job
