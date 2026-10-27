from __future__ import annotations
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict, model_validator, field_serializer

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
    policy_id: Optional[str] = 'POL-ALERTING-V1'
    event_source: str = 'LIVE_CAMERA'

    @model_validator(mode='after')
    def compute_event_source(self) -> 'PassageEventResponse':
        self.event_source = 'RECORDED_VIDEO' if self.video_job_id else 'LIVE_CAMERA'
        return self

    @field_serializer('crop_path')
    def serialize_crop_path(self, v: Optional[str]) -> Optional[str]:
        if v:
            return f"/api/v1/media/crops/{self.id}"
        return None

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
