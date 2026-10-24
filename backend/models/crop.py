from __future__ import annotations
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Float, Integer, ForeignKey
from sqlalchemy.orm import relationship
from backend.core.database import Base

def generate_uuid() -> str:
    return str(uuid.uuid4())

class RepresentativeCrop(Base):
    __tablename__ = 'representative_crops'

    id = Column(String(36), primary_key=True, default=generate_uuid)
    tenant_id = Column(String(36), ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    track_id = Column(String(36), ForeignKey('tracks.id', ondelete='SET NULL'), nullable=True, index=True)
    passage_event_id = Column(String(36), ForeignKey('passage_events.id', ondelete='SET NULL'), nullable=True, index=True)
    worker_id = Column(String(36), ForeignKey('workers.id', ondelete='SET NULL'), nullable=True, index=True)
    candidate_identity_id = Column(String(36), ForeignKey('candidate_identities.id', ondelete='SET NULL'), nullable=True, index=True)
    file_path = Column(String(512), nullable=False)
    width = Column(Integer, default=0, nullable=False)
    height = Column(Integer, default=0, nullable=False)
    blur_score = Column(Float, default=0.0, nullable=False)
    quality_score = Column(Float, default=0.0, nullable=False)
    retention_status = Column(String(32), default='RETAINED', nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    track = relationship('Track', back_populates='crops')
    passage_event = relationship('PassageEvent', back_populates='crops')
