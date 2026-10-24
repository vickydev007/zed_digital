from __future__ import annotations
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from backend.core.database import Base, CompatibleJSON

def generate_uuid() -> str:
    return str(uuid.uuid4())

class CandidateIdentity(Base):
    __tablename__ = 'candidate_identities'
    __table_args__ = (
        UniqueConstraint('tenant_id', 'candidate_code', name='uq_tenant_candidate_code'),
    )

    id = Column(String(36), primary_key=True, default=generate_uuid)
    tenant_id = Column(String(36), ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    candidate_code = Column(String(64), nullable=False, index=True)
    first_seen_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    last_seen_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    review_status = Column(String(32), default='PROVISIONAL', nullable=False)
    approved_worker_id = Column(String(36), ForeignKey('workers.id', ondelete='SET NULL'), nullable=True)
    notes = Column(String(512), nullable=True)
    metadata_json = Column(CompatibleJSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    tenant = relationship('Tenant', back_populates='candidate_identities')
    embeddings = relationship('PersonEmbedding', back_populates='candidate_identity', cascade='all, delete-orphan')
    tracks = relationship('Track', back_populates='candidate_identity')
    passage_events = relationship('PassageEvent', back_populates='candidate_identity')
