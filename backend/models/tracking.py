from __future__ import annotations
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, DateTime, Float, Integer, ForeignKey
from sqlalchemy.orm import relationship
from backend.core.database import Base

def generate_uuid() -> str:
    return str(uuid.uuid4())

class Track(Base):
    __tablename__ = 'tracks'

    id = Column(String(36), primary_key=True, default=generate_uuid)
    tenant_id = Column(String(36), ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    video_job_id = Column(String(36), ForeignKey('video_jobs.id', ondelete='CASCADE'), nullable=True, index=True)
    camera_id = Column(String(36), ForeignKey('cameras.id', ondelete='SET NULL'), nullable=True, index=True)
    track_number = Column(Integer, nullable=False)
    first_frame = Column(Integer, default=0, nullable=False)
    last_frame = Column(Integer, default=0, nullable=False)
    total_seen_frames = Column(Integer, default=1, nullable=False)
    identity_status = Column(String(32), default='UNKNOWN', nullable=False)
    passage_status = Column(String(32), default='FIRST_ENTRY', nullable=False)
    display_category = Column(String(32), default='UNKNOWN', nullable=False)
    candidate_identity_id = Column(String(36), ForeignKey('candidate_identities.id', ondelete='SET NULL'), nullable=True, index=True)
    matched_worker_id = Column(String(36), ForeignKey('workers.id', ondelete='SET NULL'), nullable=True, index=True)
    representative_crop_id = Column(String(36), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    video_job = relationship('VideoJob', back_populates='tracks')
    candidate_identity = relationship('CandidateIdentity', back_populates='tracks')
    observations = relationship('Observation', back_populates='track', cascade='all, delete-orphan')
    decisions = relationship('MatchDecision', back_populates='track', cascade='all, delete-orphan')
    crops = relationship('RepresentativeCrop', back_populates='track')
    passage_events = relationship('PassageEvent', back_populates='track')

class Observation(Base):
    __tablename__ = 'observations'

    id = Column(String(36), primary_key=True, default=generate_uuid)
    tenant_id = Column(String(36), ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    track_id = Column(String(36), ForeignKey('tracks.id', ondelete='CASCADE'), nullable=False, index=True)
    frame_idx = Column(Integer, nullable=False)
    timestamp_offset_seconds = Column(Float, default=0.0, nullable=False)
    bbox_x = Column(Integer, nullable=False)
    bbox_y = Column(Integer, nullable=False)
    bbox_w = Column(Integer, nullable=False)
    bbox_h = Column(Integer, nullable=False)
    detection_confidence = Column(Float, default=1.0, nullable=False)
    quality_score = Column(Float, default=0.0, nullable=False)
    blur_variance = Column(Float, default=0.0, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    track = relationship('Track', back_populates='observations')

class MatchDecision(Base):
    __tablename__ = 'match_decisions'

    id = Column(String(36), primary_key=True, default=generate_uuid)
    tenant_id = Column(String(36), ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    track_id = Column(String(36), ForeignKey('tracks.id', ondelete='CASCADE'), nullable=True, index=True)
    observation_id = Column(String(36), ForeignKey('observations.id', ondelete='SET NULL'), nullable=True)
    top_candidate_id = Column(String(64), nullable=True)
    top_candidate_score = Column(Float, default=0.0, nullable=False)
    runner_up_score = Column(Float, default=0.0, nullable=False)
    score_margin = Column(Float, default=0.0, nullable=False)
    policy_id = Column(String(64), default='POL-ALERTING-V1', nullable=False)
    score_threshold = Column(Float, default=0.85, nullable=False)
    contrast_margin = Column(Float, default=0.10, nullable=False)
    decision_category = Column(String(32), default='UNKNOWN', nullable=False)
    is_accepted = Column(Boolean, default=False, nullable=False)
    rejection_reason = Column(String(255), nullable=True)
    model_version = Column(String(64), default='v5.0-multigranularity-hardmining', nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    track = relationship('Track', back_populates='decisions')
