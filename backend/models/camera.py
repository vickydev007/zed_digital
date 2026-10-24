from __future__ import annotations
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, DateTime, Float, ForeignKey
from sqlalchemy.orm import relationship
from backend.core.database import Base

def generate_uuid() -> str:
    return str(uuid.uuid4())

class Camera(Base):
    __tablename__ = 'cameras'

    id = Column(String(36), primary_key=True, default=generate_uuid)
    tenant_id = Column(String(36), ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    name = Column(String(120), nullable=False)
    location = Column(String(255), nullable=True)
    rtsp_url_encrypted = Column(String(1024), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    status = Column(String(32), default='OFFLINE', nullable=False)
    stream_fps = Column(Float, default=25.0, nullable=False)
    last_heartbeat = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    tenant = relationship('Tenant', back_populates='cameras')
    credentials = relationship('CameraCredential', back_populates='camera', cascade='all, delete-orphan')

class CameraCredential(Base):
    __tablename__ = 'camera_credentials'

    id = Column(String(36), primary_key=True, default=generate_uuid)
    camera_id = Column(String(36), ForeignKey('cameras.id', ondelete='CASCADE'), nullable=False, index=True)
    auth_type = Column(String(32), default='BASIC', nullable=False)
    username = Column(String(120), nullable=True)
    encrypted_secret = Column(String(1024), nullable=False)
    kms_reference = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    camera = relationship('Camera', back_populates='credentials')
