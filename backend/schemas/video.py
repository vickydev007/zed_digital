from __future__ import annotations
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict

class VideoAssetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    camera_id: Optional[str] = None
    original_filename: str
    mime_type: str
    file_size_bytes: int
    duration_seconds: float
    fps: Optional[float] = 25.0
    frame_count: Optional[int] = 0
    resolution_width: Optional[int] = 0
    resolution_height: Optional[int] = 0
    validation_status: str
    created_at: datetime

class VideoAnalyzeRequest(BaseModel):
    score_threshold: Optional[float] = 0.85
    contrast_margin: Optional[float] = 0.10
    max_frames: Optional[int] = None
    auto_enroll_lead_worker: bool = True
    save_annotated_video: bool = True
