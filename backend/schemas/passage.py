from __future__ import annotations
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict

class PassageEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    camera_id: Optional[str] = None
    video_job_id: Optional[str] = None
    track_id: Optional[str] = None
    worker_id: Optional[str] = None
    candidate_identity_id: Optional[str] = None
    identity_status: str
    passage_status: str
    display_category: str
    confidence_score: float
    crop_path: Optional[str] = None
    event_timestamp: datetime
    is_reviewed: bool
    created_at: datetime

class PresenceSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    worker_id: Optional[str] = None
    candidate_identity_id: Optional[str] = None
    identity_status: str
    session_start: datetime
    session_end: Optional[datetime] = None
    is_currently_present: bool
    last_seen_camera_id: Optional[str] = None
    passage_count: int
    created_at: datetime
    updated_at: datetime
