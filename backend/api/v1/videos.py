from __future__ import annotations
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.models.tenant import User, Tenant
from backend.schemas.video import VideoAssetResponse, VideoAnalyzeRequest
from backend.schemas.job import JobResponse
from backend.services.video_service import (
    save_uploaded_video,
    get_video_by_id,
    list_videos,
    create_analysis_job
)
from backend.api.deps import get_current_user, get_current_tenant, require_operator

router = APIRouter(prefix='/videos', tags=['Videos'])

@router.post('/upload', response_model=VideoAssetResponse, status_code=status.HTTP_201_CREATED)
async def upload_video_file(
    file: UploadFile = File(...),
    camera_id: Optional[str] = Query(None),
    current_tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    _auth: bool = Depends(require_operator),
    db: Session = Depends(get_db)
):
    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Uploaded video file is empty')
    
    try:
        asset = save_uploaded_video(
            db=db,
            tenant_id=current_tenant.id,
            file_bytes=content,
            original_filename=file.filename or 'uploaded_video.mp4',
            camera_id=camera_id,
            user_id=current_user.id
        )
        return VideoAssetResponse.model_validate(asset)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

@router.get('', response_model=List[VideoAssetResponse])
def get_videos(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    videos, _ = list_videos(db, current_tenant.id, skip=skip, limit=limit)
    return [VideoAssetResponse.model_validate(v) for v in videos]

@router.get('/{video_id}', response_model=VideoAssetResponse)
def get_video_metadata(
    video_id: str,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    asset = get_video_by_id(db, current_tenant.id, video_id)
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video asset '{video_id}' not found in this tenant"
        )
    return VideoAssetResponse.model_validate(asset)

@router.post('/{video_id}/analyze', response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
def request_video_analysis(
    video_id: str,
    data: VideoAnalyzeRequest = VideoAnalyzeRequest(),
    current_tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    _auth: bool = Depends(require_operator),
    db: Session = Depends(get_db)
):
    try:
        job = create_analysis_job(
            db=db,
            tenant_id=current_tenant.id,
            video_asset_id=video_id,
            options=data,
            user_id=current_user.id
        )
        return JobResponse.model_validate(job)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
