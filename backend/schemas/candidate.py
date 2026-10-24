from __future__ import annotations
from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, ConfigDict

class CandidateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    candidate_code: str
    first_seen_at: datetime
    last_seen_at: datetime
    review_status: str
    approved_worker_id: Optional[str] = None
    notes: Optional[str] = None
    metadata_json: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

class CandidateReviewRequest(BaseModel):
    review_status: str
    notes: Optional[str] = None
    approved_worker_id: Optional[str] = None
