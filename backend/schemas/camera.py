from __future__ import annotations
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict

class CameraCreateRequest(BaseModel):
    name: str
    location: Optional[str] = None
    rtsp_url: Optional[str] = None
    stream_fps: float = 25.0

class CameraUpdateRequest(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None
    rtsp_url: Optional[str] = None
    stream_fps: Optional[float] = None
    is_active: Optional[bool] = None

class CameraResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    name: str
    location: Optional[str] = None
    is_active: bool
    status: str
    stream_fps: float
    last_heartbeat: Optional[datetime] = None
    has_encrypted_stream: bool
    created_at: datetime
    updated_at: datetime

class CameraActionResponse(BaseModel):
    id: str
    name: str
    status: str
    action_performed: str
