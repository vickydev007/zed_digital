from __future__ import annotations
import os
from typing import Tuple, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select
from fastapi import HTTPException, status
from backend.models.crop import RepresentativeCrop
from backend.models.video import VideoAsset, VideoJob
from backend.models.worker import Worker, EnrollmentImage
from backend.core.config import settings

def _validate_safe_path(file_path: str, base_dirs: list[str]) -> str:
    abs_path = os.path.abspath(file_path)
    is_safe = False
    for base in base_dirs:
        abs_base = os.path.abspath(base)
        try:
            if os.path.commonpath([abs_path, abs_base]) == abs_base:
                is_safe = True
                break
        except ValueError:
            continue
    if not is_safe or not os.path.exists(abs_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Media file not found or inaccessible'
        )
    return abs_path

def get_authorized_crop_file(db: Session, tenant_id: str, crop_id: str) -> Tuple[str, str]:
    stmt = select(RepresentativeCrop).where(RepresentativeCrop.tenant_id == tenant_id, RepresentativeCrop.id == crop_id)
    crop = db.execute(stmt).scalar_one_or_none()
    if not crop or not crop.file_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Crop record not found')
    safe_path = _validate_safe_path(crop.file_path, [settings.CROPS_DIR])
    return safe_path, 'image/jpeg'

def get_authorized_video_file(db: Session, tenant_id: str, video_id: str) -> Tuple[str, str]:
    stmt = select(VideoAsset).where(VideoAsset.tenant_id == tenant_id, VideoAsset.id == video_id)
    asset = db.execute(stmt).scalar_one_or_none()
    if not asset or not asset.stored_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Video asset not found')
    safe_path = _validate_safe_path(asset.stored_path, [settings.UPLOAD_DIR])
    return safe_path, 'video/mp4'

def get_authorized_job_video_file(db: Session, tenant_id: str, job_id: str) -> Tuple[str, str]:
    stmt = select(VideoJob).where(VideoJob.tenant_id == tenant_id, VideoJob.id == job_id)
    job = db.execute(stmt).scalar_one_or_none()
    if not job or not job.output_video_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Annotated output video not found')
    safe_path = _validate_safe_path(job.output_video_path, [settings.OUTPUT_VIDEOS_DIR])
    return safe_path, 'video/mp4'

def get_authorized_enrollment_image_file(db: Session, tenant_id: str, worker_id: str, image_id: str) -> Tuple[str, str]:
    w_stmt = select(Worker).where(Worker.tenant_id == tenant_id, Worker.id == worker_id)
    worker = db.execute(w_stmt).scalar_one_or_none()
    if not worker:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Worker not found')
    img_stmt = select(EnrollmentImage).where(EnrollmentImage.worker_id == worker.id, EnrollmentImage.id == image_id)
    enroll_img = db.execute(img_stmt).scalar_one_or_none()
    if not enroll_img or not enroll_img.image_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Enrollment image not found')
    safe_path = _validate_safe_path(enroll_img.image_path, [settings.CROPS_DIR])
    return safe_path, 'image/jpeg'
