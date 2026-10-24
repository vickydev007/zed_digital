from __future__ import annotations
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, DateTime, Float, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from backend.core.database import Base, CompatibleJSON

def generate_uuid() -> str:
    return str(uuid.uuid4())

class Worker(Base):
    __tablename__ = 'workers'
    __table_args__ = (
        UniqueConstraint('tenant_id', 'staff_code', name='uq_tenant_worker_staff_code'),
    )

    id = Column(String(36), primary_key=True, default=generate_uuid)
    tenant_id = Column(String(36), ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    staff_code = Column(String(64), nullable=False, index=True)
    full_name = Column(String(120), nullable=False)
    batch = Column(String(64), nullable=True)
    department = Column(String(120), nullable=True)
    uniform_category = Column(String(64), nullable=True)
    enrollment_status = Column(String(32), default='ENROLLED', nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    tenant = relationship('Tenant', back_populates='workers')
    enrollment_images = relationship('EnrollmentImage', back_populates='worker', cascade='all, delete-orphan')
    embeddings = relationship('PersonEmbedding', back_populates='worker', cascade='all, delete-orphan')
    passage_events = relationship('PassageEvent', back_populates='worker')

class EnrollmentImage(Base):
    __tablename__ = 'enrollment_images'

    id = Column(String(36), primary_key=True, default=generate_uuid)
    worker_id = Column(String(36), ForeignKey('workers.id', ondelete='CASCADE'), nullable=False, index=True)
    image_path = Column(String(512), nullable=False)
    file_hash = Column(String(64), nullable=True)
    blur_score = Column(Float, default=0.0, nullable=False)
    quality_score = Column(Float, default=0.0, nullable=False)
    is_primary = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    worker = relationship('Worker', back_populates='enrollment_images')

class PersonEmbedding(Base):
    __tablename__ = 'person_embeddings'

    id = Column(String(36), primary_key=True, default=generate_uuid)
    tenant_id = Column(String(36), ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    worker_id = Column(String(36), ForeignKey('workers.id', ondelete='CASCADE'), nullable=True, index=True)
    candidate_identity_id = Column(String(36), ForeignKey('candidate_identities.id', ondelete='CASCADE'), nullable=True, index=True)
    enrollment_image_id = Column(String(36), ForeignKey('enrollment_images.id', ondelete='SET NULL'), nullable=True)
    observation_id = Column(String(36), nullable=True)
    embedding_vector = Column(CompatibleJSON, nullable=False)
    dimension = Column(Integer, default=512, nullable=False)
    embedding_version = Column(String(32), default='v1.0-onnx', nullable=False)
    model_version = Column(String(32), default='best_model.pth', nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    worker = relationship('Worker', back_populates='embeddings')
    candidate_identity = relationship('CandidateIdentity', back_populates='embeddings')
