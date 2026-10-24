from __future__ import annotations
from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, ConfigDict

class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    video_asset_id: str
    job_type: str
    status: str
    progress_percent: float
    error_details: Optional[str] = None
    summary_json: Optional[Dict[str, Any]] = None
    output_video_path: Optional[str] = None
    output_crops_dir: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

class JobProgressResponse(BaseModel):
    id: str
    status: str
    progress_percent: float
    completed_at: Optional[datetime] = None
    error_details: Optional[str] = None
