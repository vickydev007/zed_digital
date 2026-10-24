from __future__ import annotations
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from backend.core.database import Base

def generate_uuid() -> str:
    return str(uuid.uuid4())

class Tenant(Base):
    __tablename__ = 'tenants'

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(120), nullable=False)
    slug = Column(String(120), unique=True, index=True, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    memberships = relationship('TenantMembership', back_populates='tenant', cascade='all, delete-orphan')
    workers = relationship('Worker', back_populates='tenant', cascade='all, delete-orphan')
    cameras = relationship('Camera', back_populates='tenant', cascade='all, delete-orphan')
    candidate_identities = relationship('CandidateIdentity', back_populates='tenant', cascade='all, delete-orphan')
    video_assets = relationship('VideoAsset', back_populates='tenant', cascade='all, delete-orphan')
    video_jobs = relationship('VideoJob', back_populates='tenant', cascade='all, delete-orphan')
    passage_events = relationship('PassageEvent', back_populates='tenant', cascade='all, delete-orphan')

class User(Base):
    __tablename__ = 'users'

    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(120), nullable=False)
    is_superuser = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    memberships = relationship('TenantMembership', back_populates='user', cascade='all, delete-orphan')

class TenantMembership(Base):
    __tablename__ = 'tenant_memberships'
    __table_args__ = (
        UniqueConstraint('tenant_id', 'user_id', name='uq_tenant_user_membership'),
    )

    id = Column(String(36), primary_key=True, default=generate_uuid)
    tenant_id = Column(String(36), ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    role = Column(String(32), default='OPERATOR', nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    tenant = relationship('Tenant', back_populates='memberships')
    user = relationship('User', back_populates='memberships')
