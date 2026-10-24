from __future__ import annotations
from typing import List, Dict
from pydantic import BaseModel
from backend.schemas.passage import PassageEventResponse

class DashboardStatsResponse(BaseModel):
    active_workers_present: int
    qualifying_candidates_count: int
    repeat_passages_count: int
    unknown_observations_count: int
    total_passage_events: int
    active_cameras_count: int
    active_jobs_count: int
    category_counts: Dict[str, int]
    recent_events: List[PassageEventResponse]
