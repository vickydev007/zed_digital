from __future__ import annotations
from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, ConfigDict, field_serializer

class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    video_asset_id: str
    job_type: str
    status: str
    progress_percent: float
    processed_frames: Optional[int] = 0
    total_frames: Optional[int] = 0
    error_details: Optional[str] = None
    summary_json: Optional[Dict[str, Any]] = None
    output_video_path: Optional[str] = None
    output_crops_dir: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    @field_serializer('output_video_path')
    def serialize_output_video_path(self, v: Optional[str]) -> Optional[str]:
        if v:
            return f"/api/v1/media/jobs/{self.id}/video"
        return None

    @field_serializer('output_crops_dir')
    def serialize_output_crops_dir(self, v: Optional[str]) -> Optional[str]:
        if v:
            return f"/api/v1/media/jobs/{self.id}/crops"
        return None

class JobProgressResponse(BaseModel):
    id: str
    status: str
    progress_percent: float
    processed_frames: Optional[int] = 0
    total_frames: Optional[int] = 0
    completed_at: Optional[datetime] = None
    error_details: Optional[str] = None
