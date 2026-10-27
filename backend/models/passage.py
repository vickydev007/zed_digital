from __future__ import annotations
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, DateTime, Float, Integer, ForeignKey
from sqlalchemy.orm import relationship
from backend.core.database import Base

def generate_uuid() -> str:
    return str(uuid.uuid4())

class PassageEvent(Base):
    __tablename__ = 'passage_events'

    id = Column(String(36), primary_key=True, default=generate_uuid)
    tenant_id = Column(String(36), ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    camera_id = Column(String(36), ForeignKey('cameras.id', ondelete='SET NULL'), nullable=True, index=True)
    video_job_id = Column(String(36), ForeignKey('video_jobs.id', ondelete='CASCADE'), nullable=True, index=True)
    track_id = Column(String(36), ForeignKey('tracks.id', ondelete='SET NULL'), nullable=True, index=True)
    worker_id = Column(String(36), ForeignKey('workers.id', ondelete='SET NULL'), nullable=True, index=True)
    candidate_identity_id = Column(String(36), ForeignKey('candidate_identities.id', ondelete='SET NULL'), nullable=True, index=True)
    identity_status = Column(String(32), nullable=False)
    passage_status = Column(String(32), nullable=False)
    display_category = Column(String(32), nullable=False)
    confidence_score = Column(Float, default=0.0, nullable=False)
    policy_id = Column(String(64), default='POL-ALERTING-V1', nullable=False)
    crop_path = Column(String(512), nullable=True)
    event_timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    is_reviewed = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    tenant = relationship('Tenant', back_populates='passage_events')
    video_job = relationship('VideoJob', back_populates='passage_events')
    track = relationship('Track', back_populates='passage_events')
    worker = relationship('Worker', back_populates='passage_events')
    candidate_identity = relationship('CandidateIdentity', back_populates='passage_events')
    crops = relationship('RepresentativeCrop', back_populates='passage_event')

class PresenceSession(Base):
    __tablename__ = 'presence_sessions'

    id = Column(String(36), primary_key=True, default=generate_uuid)
    tenant_id = Column(String(36), ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    worker_id = Column(String(36), ForeignKey('workers.id', ondelete='SET NULL'), nullable=True, index=True)
    candidate_identity_id = Column(String(36), ForeignKey('candidate_identities.id', ondelete='SET NULL'), nullable=True, index=True)
    identity_status = Column(String(32), nullable=False)
    session_start = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    session_end = Column(DateTime(timezone=True), nullable=True)
    is_currently_present = Column(Boolean, default=True, nullable=False)
    last_seen_camera_id = Column(String(36), ForeignKey('cameras.id', ondelete='SET NULL'), nullable=True)
    passage_count = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
