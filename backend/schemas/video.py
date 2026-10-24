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
    stored_path: str
    mime_type: str
    file_size_bytes: int
    duration_seconds: float
    validation_status: str
    created_at: datetime

class VideoAnalyzeRequest(BaseModel):
    score_threshold: Optional[float] = 0.7124
    contrast_margin: Optional[float] = 0.05
    max_frames: Optional[int] = None
    auto_enroll_lead_worker: bool = True
