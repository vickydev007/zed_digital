from __future__ import annotations
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from backend.models.passage import PassageEvent, PresenceSession
from backend.models.candidate import CandidateIdentity
from backend.models.camera import Camera
from backend.models.video import VideoJob
from backend.schemas.dashboard import DashboardStatsResponse
from backend.schemas.passage import PassageEventResponse
from openset_reid.pipeline.video_analyzer import PersonCategory

def get_dashboard_stats(db: Session, tenant_id: str) -> DashboardStatsResponse:
    workers_present_stmt = select(func.count(PresenceSession.id)).where(
        PresenceSession.tenant_id == tenant_id,
        PresenceSession.is_currently_present == True,
        PresenceSession.worker_id.isnot(None)
    )
    workers_present = db.scalar(workers_present_stmt) or 0

    candidates_stmt = select(func.count(CandidateIdentity.id)).where(
        CandidateIdentity.tenant_id == tenant_id
    )
    candidates_count = db.scalar(candidates_stmt) or 0

    repeat_passages_stmt = select(func.count(PassageEvent.id)).where(
        PassageEvent.tenant_id == tenant_id,
        PassageEvent.passage_status == 'REPEAT_PASSAGE'
    )
    repeat_passages = db.scalar(repeat_passages_stmt) or 0

    unknown_stmt = select(func.count(PassageEvent.id)).where(
        PassageEvent.tenant_id == tenant_id,
        PassageEvent.identity_status == 'UNKNOWN'
    )
    unknown_count = db.scalar(unknown_stmt) or 0

    total_events_stmt = select(func.count(PassageEvent.id)).where(
        PassageEvent.tenant_id == tenant_id
    )
    total_events = db.scalar(total_events_stmt) or 0

    active_cameras_stmt = select(func.count(Camera.id)).where(
        Camera.tenant_id == tenant_id,
        Camera.is_active == True,
        Camera.status == 'ONLINE'
    )
    active_cameras = db.scalar(active_cameras_stmt) or 0

    active_jobs_stmt = select(func.count(VideoJob.id)).where(
        VideoJob.tenant_id == tenant_id,
        VideoJob.status.in_(['QUEUED', 'RUNNING'])
    )
    active_jobs = db.scalar(active_jobs_stmt) or 0

    category_counts = {
        PersonCategory.OFFICIAL_WORKER.value: 0,
        PersonCategory.NEW_PERSON.value: 0,
        PersonCategory.PREVIOUSLY_ENROLLED.value: 0,
        PersonCategory.UNKNOWN.value: 0
    }

    cat_stmt = select(PassageEvent.display_category, func.count(PassageEvent.id)).where(
        PassageEvent.tenant_id == tenant_id
    ).group_by(PassageEvent.display_category)
    cat_rows = db.execute(cat_stmt).all()
    for cat_name, cnt in cat_rows:
        if cat_name in category_counts:
            category_counts[cat_name] = cnt

    recent_events_stmt = select(PassageEvent).where(
        PassageEvent.tenant_id == tenant_id
    ).order_by(PassageEvent.event_timestamp.desc()).limit(10)
    recent_events_models = list(db.execute(recent_events_stmt).scalars().all())
    recent_events = [PassageEventResponse.model_validate(ev) for ev in recent_events_models]

    return DashboardStatsResponse(
        active_workers_present=workers_present,
        qualifying_candidates_count=candidates_count,
        repeat_passages_count=repeat_passages,
        unknown_observations_count=unknown_count,
        total_passage_events=total_events,
        active_cameras_count=active_cameras,
        active_jobs_count=active_jobs,
        category_counts=category_counts,
        recent_events=recent_events
    )
