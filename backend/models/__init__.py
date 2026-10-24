from __future__ import annotations
from backend.core.database import Base, CompatibleJSON
from backend.models.tenant import Tenant, User, TenantMembership
from backend.models.camera import Camera, CameraCredential
from backend.models.worker import Worker, EnrollmentImage, PersonEmbedding
from backend.models.candidate import CandidateIdentity
from backend.models.video import VideoAsset, VideoJob
from backend.models.tracking import Track, Observation, MatchDecision
from backend.models.passage import PassageEvent, PresenceSession
from backend.models.crop import RepresentativeCrop
from backend.models.audit import AuditLog, ExperimentRun, EvaluationResult

__all__ = [
    'Base',
    'CompatibleJSON',
    'Tenant',
    'User',
    'TenantMembership',
    'Camera',
    'CameraCredential',
    'Worker',
    'EnrollmentImage',
    'PersonEmbedding',
    'CandidateIdentity',
    'VideoAsset',
    'VideoJob',
    'Track',
    'Observation',
    'MatchDecision',
    'PassageEvent',
    'PresenceSession',
    'RepresentativeCrop',
    'AuditLog',
    'ExperimentRun',
    'EvaluationResult',
]
