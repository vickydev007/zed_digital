from __future__ import annotations
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Float, Integer, ForeignKey
from sqlalchemy.orm import relationship
from backend.core.database import Base, CompatibleJSON

def generate_uuid() -> str:
    return str(uuid.uuid4())

class VideoAsset(Base):
    __tablename__ = 'video_assets'

    id = Column(String(36), primary_key=True, default=generate_uuid)
    tenant_id = Column(String(36), ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    camera_id = Column(String(36), ForeignKey('cameras.id', ondelete='SET NULL'), nullable=True)
    original_filename = Column(String(255), nullable=False)
    stored_path = Column(String(512), nullable=False)
    mime_type = Column(String(64), default='video/mp4', nullable=False)
    file_size_bytes = Column(Integer, default=0, nullable=False)
    duration_seconds = Column(Float, default=0.0, nullable=False)
    validation_status = Column(String(32), default='VALIDATED', nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    tenant = relationship('Tenant', back_populates='video_assets')
    jobs = relationship('VideoJob', back_populates='video_asset', cascade='all, delete-orphan')

class VideoJob(Base):
    __tablename__ = 'video_jobs'

    id = Column(String(36), primary_key=True, default=generate_uuid)
    tenant_id = Column(String(36), ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    video_asset_id = Column(String(36), ForeignKey('video_assets.id', ondelete='CASCADE'), nullable=False, index=True)
    job_type = Column(String(32), default='OFFLINE_REID', nullable=False)
    status = Column(String(32), default='QUEUED', nullable=False, index=True)
    progress_percent = Column(Float, default=0.0, nullable=False)
    error_details = Column(String(1024), nullable=True)
    summary_json = Column(CompatibleJSON, nullable=True)
    output_video_path = Column(String(512), nullable=True)
    output_crops_dir = Column(String(512), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    tenant = relationship('Tenant', back_populates='video_jobs')
    video_asset = relationship('VideoAsset', back_populates='jobs')
    tracks = relationship('Track', back_populates='video_job', cascade='all, delete-orphan')
    passage_events = relationship('PassageEvent', back_populates='video_job', cascade='all, delete-orphan')
