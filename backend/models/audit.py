from __future__ import annotations
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Float, ForeignKey
from sqlalchemy.orm import relationship
from backend.core.database import Base, CompatibleJSON

def generate_uuid() -> str:
    return str(uuid.uuid4())

class AuditLog(Base):
    __tablename__ = 'audit_logs'

    id = Column(String(36), primary_key=True, default=generate_uuid)
    tenant_id = Column(String(36), ForeignKey('tenants.id', ondelete='SET NULL'), nullable=True, index=True)
    user_id = Column(String(36), ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    action = Column(String(64), nullable=False)
    entity_type = Column(String(64), nullable=False)
    entity_id = Column(String(64), nullable=True)
    ip_address = Column(String(64), nullable=True)
    details_json = Column(CompatibleJSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

class ExperimentRun(Base):
    __tablename__ = 'experiment_runs'

    id = Column(String(36), primary_key=True, default=generate_uuid)
    tenant_id = Column(String(36), ForeignKey('tenants.id', ondelete='SET NULL'), nullable=True, index=True)
    experiment_name = Column(String(128), nullable=False)
    model_name = Column(String(128), nullable=False)
    model_version = Column(String(64), nullable=False)
    dataset_split = Column(String(64), nullable=False)
    score_threshold = Column(Float, default=0.7124, nullable=False)
    contrast_margin = Column(Float, default=0.05, nullable=False)
    evaluation_protocol = Column(String(128), default='Open-Set Re-ID Market-1501', nullable=False)
    metadata_json = Column(CompatibleJSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    results = relationship('EvaluationResult', back_populates='experiment_run', cascade='all, delete-orphan')

class EvaluationResult(Base):
    __tablename__ = 'evaluation_results'

    id = Column(String(36), primary_key=True, default=generate_uuid)
    experiment_run_id = Column(String(36), ForeignKey('experiment_runs.id', ondelete='CASCADE'), nullable=False, index=True)
    metric_name = Column(String(64), nullable=False)
    metric_value = Column(Float, nullable=False)
    confidence_interval_low = Column(Float, nullable=True)
    confidence_interval_high = Column(Float, nullable=True)
    details_json = Column(CompatibleJSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    experiment_run = relationship('ExperimentRun', back_populates='results')
