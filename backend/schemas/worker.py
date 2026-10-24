from __future__ import annotations
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, ConfigDict

class WorkerCreateRequest(BaseModel):
    staff_code: str
    full_name: str
    batch: Optional[str] = None
    department: Optional[str] = None
    uniform_category: Optional[str] = None

class WorkerUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    batch: Optional[str] = None
    department: Optional[str] = None
    uniform_category: Optional[str] = None
    enrollment_status: Optional[str] = None
    is_active: Optional[bool] = None

class EnrollmentImageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    worker_id: str
    image_path: str
    blur_score: float
    quality_score: float
    is_primary: bool
    created_at: datetime

class WorkerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    staff_code: str
    full_name: str
    batch: Optional[str] = None
    department: Optional[str] = None
    uniform_category: Optional[str] = None
    enrollment_status: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    images: List[EnrollmentImageResponse] = []

class WorkerEnrollResponse(BaseModel):
    worker_id: str
    image_id: str
    embedding_id: str
    blur_score: float
    quality_score: float
    is_accepted: bool
    quality_passed: bool
