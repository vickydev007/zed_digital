from __future__ import annotations
from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.models.tenant import Tenant
from backend.services.media_service import (
    get_authorized_crop_file,
    get_authorized_video_file,
    get_authorized_job_video_file,
    get_authorized_enrollment_image_file
)
from backend.api.deps import get_current_tenant

router = APIRouter(prefix='/media', tags=['Authorized Media'])

@router.get('/crops/{crop_id}')
def download_crop(
    crop_id: str,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    file_path, media_type = get_authorized_crop_file(db, current_tenant.id, crop_id)
    return FileResponse(file_path, media_type=media_type)

@router.get('/videos/{video_id}')
def download_video(
    video_id: str,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    file_path, media_type = get_authorized_video_file(db, current_tenant.id, video_id)
    return FileResponse(file_path, media_type=media_type)

@router.get('/jobs/{job_id}/video')
def download_job_output_video(
    job_id: str,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    file_path, media_type = get_authorized_job_video_file(db, current_tenant.id, job_id)
    return FileResponse(file_path, media_type=media_type)

@router.get('/workers/{worker_id}/images/{image_id}')
def download_enrollment_image(
    worker_id: str,
    image_id: str,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    file_path, media_type = get_authorized_enrollment_image_file(db, current_tenant.id, worker_id, image_id)
    return FileResponse(file_path, media_type=media_type)
