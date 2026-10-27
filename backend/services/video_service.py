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

    mime_map = {
        '.mp4': 'video/mp4',
        '.avi': 'video/x-msvideo',
        '.mov': 'video/quicktime',
        '.mkv': 'video/x-matroska',
        '.webm': 'video/webm'
    }
    mime_type = mime_map.get(file_ext, 'video/mp4')

    target_dir = os.path.join(settings.UPLOAD_DIR, tenant_id)
    os.makedirs(target_dir, exist_ok=True)
    stored_name = f"{uuid.uuid4()}{file_ext}"
    stored_path = os.path.join(target_dir, stored_name)

    with open(stored_path, 'wb') as f:
        f.write(file_bytes)

    cap = cv2.VideoCapture(stored_path)
    if not cap.isOpened():
        if os.path.exists(stored_path):
            os.remove(stored_path)
        raise ValueError(f"Invalid or corrupt video container: unable to open media stream from '{original_filename}'.")

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    ret, test_frame = cap.read()
    cap.release()

    if not ret or test_frame is None or frame_count <= 0 or w <= 0 or h <= 0:
        if os.path.exists(stored_path):
            os.remove(stored_path)
        raise ValueError(f"Corrupt or truncated video file: could not decode video frames from '{original_filename}'.")

    duration = float(frame_count / max(1.0, fps))
    if duration <= 0.0:
        if os.path.exists(stored_path):
            os.remove(stored_path)
        raise ValueError("Video duration cannot be zero or negative.")

    MAX_VIDEO_DURATION_SECONDS = 3600.0
    if duration > MAX_VIDEO_DURATION_SECONDS:
        if os.path.exists(stored_path):
            os.remove(stored_path)
        raise ValueError(f"Video duration ({duration:.1f}s) exceeds maximum allowed limit of {MAX_VIDEO_DURATION_SECONDS:.0f} seconds (1 hour).")

    asset = VideoAsset(
        tenant_id=tenant_id,
        camera_id=camera_id,
        original_filename=original_filename,
        stored_path=stored_path,
        mime_type=mime_type,
        file_size_bytes=file_size,
        duration_seconds=round(duration, 2),
        fps=round(float(fps), 2),
        frame_count=frame_count,
        resolution_width=w,
        resolution_height=h,
        validation_status='VALIDATED'
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
        details={
            'filename': original_filename,
            'size_bytes': file_size,
            'status': 'VALIDATED',
            'resolution': f"{w}x{h}",
            'duration_seconds': round(duration, 2),
            'fps': round(float(fps), 2),
            'frame_count': frame_count
        }
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
