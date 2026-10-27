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

class CameraRuntimeStatusResponse(BaseModel):
    camera_id: str
    tenant_id: str
    status: str
    received_fps: float
    processed_fps: float
    received_frames: int
    processed_frames: int
    active_tracks: int
    reconnect_count: int
    last_frame_time: Optional[str] = None
    last_error: Optional[str] = None
    uptime_seconds: float
    consumer_count: int
    sanitized_url: Optional[str] = None
    persistence_stats: Optional[dict] = None
    latency_summary: Optional[dict] = None
    policy_id: Optional[str] = None
    operating_tau: Optional[float] = None
    operating_margin: Optional[float] = None
    camera_profile: Optional[str] = None

class CameraTestConnectionRequest(BaseModel):
    rtsp_url: str

class CameraTestConnectionResponse(BaseModel):
    success: bool
    width: Optional[int] = 0
    height: Optional[int] = 0
    fps: Optional[float] = 0.0
    message: Optional[str] = None
    error: Optional[str] = None

class CameraPreviewTokenResponse(BaseModel):
    preview_token: str
    expires_in_seconds: int = 120
    camera_id: str
    tenant_id: str

class ClientLatencyReportRequest(BaseModel):
    frame_idx: int
    capture_timestamp: float
    display_timestamp: float
    display_latency_ms: float

