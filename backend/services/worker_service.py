from __future__ import annotations
import os
import uuid
import hashlib
from typing import Optional, List, Tuple
import cv2
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from backend.models.worker import Worker, EnrollmentImage, PersonEmbedding
from backend.schemas.worker import WorkerCreateRequest, WorkerUpdateRequest
from backend.core.config import settings
from backend.services.audit_service import log_audit_event
from openset_reid.deployment.onnx_inference import ONNXReIDEngine

_reid_engine: Optional[ONNXReIDEngine] = None

def get_reid_engine() -> ONNXReIDEngine:
    global _reid_engine
    if _reid_engine is None:
        model_path = settings.ONNX_MODEL_PATH
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model file not found at '{model_path}'")
        _reid_engine = ONNXReIDEngine(model_path)
    return _reid_engine

def assess_image_quality(img_bgr: np.ndarray) -> Tuple[bool, float, float]:
    h, w = img_bgr.shape[:2]
    if h < settings.DEFAULT_QUALITY_MIN_H or w < settings.DEFAULT_QUALITY_MIN_W:
        return False, 0.0, 0.0
    aspect = h / max(1, w)
    if aspect < 1.0 or aspect > 4.5:
        return False, 0.0, 0.0
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    blur_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    is_ok = (h >= settings.DEFAULT_QUALITY_MIN_H and w >= settings.DEFAULT_QUALITY_MIN_W and blur_var >= settings.DEFAULT_QUALITY_MIN_BLUR)
    norm_res = min(1.0, (h * w) / (128.0 * 256.0))
    norm_sharp = min(1.0, blur_var / 250.0)
    quality_score = 0.5 * norm_res + 0.5 * norm_sharp
    return is_ok, blur_var, quality_score

def list_workers(
    db: Session,
    tenant_id: str,
    skip: int = 0,
    limit: int = 50,
    search: Optional[str] = None,
    department: Optional[str] = None,
    is_active: Optional[bool] = None
) -> Tuple[List[Worker], int]:
    stmt = select(Worker).where(Worker.tenant_id == tenant_id)
    if is_active is not None:
        stmt = stmt.where(Worker.is_active == is_active)
    if department:
        stmt = stmt.where(Worker.department == department)
    if search:
        search_filter = f"%{search}%"
        stmt = stmt.where((Worker.full_name.ilike(search_filter)) | (Worker.staff_code.ilike(search_filter)))
    
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    workers = list(db.execute(stmt.offset(skip).limit(limit).order_by(Worker.created_at.desc())).scalars().all())
    return workers, total

def get_worker_by_id(db: Session, tenant_id: str, worker_id: str) -> Optional[Worker]:
    stmt = select(Worker).where(Worker.tenant_id == tenant_id, Worker.id == worker_id)
    return db.execute(stmt).scalar_one_or_none()

def get_worker_by_staff_code(db: Session, tenant_id: str, staff_code: str) -> Optional[Worker]:
    stmt = select(Worker).where(Worker.tenant_id == tenant_id, Worker.staff_code == staff_code.strip())
    return db.execute(stmt).scalar_one_or_none()

def create_worker(db: Session, tenant_id: str, data: WorkerCreateRequest, user_id: Optional[str] = None) -> Worker:
    existing = get_worker_by_staff_code(db, tenant_id, data.staff_code)
    if existing:
        raise ValueError(f"Worker with staff code '{data.staff_code}' already exists in this tenant.")
    
    worker = Worker(
        tenant_id=tenant_id,
        staff_code=data.staff_code.strip(),
        full_name=data.full_name.strip(),
        batch=data.batch.strip() if data.batch else None,
        department=data.department.strip() if data.department else None,
        uniform_category=data.uniform_category.strip() if data.uniform_category else None,
        enrollment_status='PENDING_REVIEW',
        is_active=True
    )
    db.add(worker)
    db.commit()
    db.refresh(worker)
    
    log_audit_event(
        db=db,
        action='CREATE_WORKER',
        entity_type='WORKER',
        entity_id=worker.id,
        tenant_id=tenant_id,
        user_id=user_id,
        details={'staff_code': worker.staff_code, 'name': worker.full_name}
    )
    return worker

def update_worker(db: Session, tenant_id: str, worker_id: str, data: WorkerUpdateRequest, user_id: Optional[str] = None) -> Worker:
    worker = get_worker_by_id(db, tenant_id, worker_id)
    if not worker:
        raise ValueError(f"Worker '{worker_id}' not found.")
    
    if data.full_name is not None:
        worker.full_name = data.full_name.strip()
    if data.batch is not None:
        worker.batch = data.batch.strip()
    if data.department is not None:
        worker.department = data.department.strip()
    if data.uniform_category is not None:
        worker.uniform_category = data.uniform_category.strip()
    if data.enrollment_status is not None:
        worker.enrollment_status = data.enrollment_status
    if data.is_active is not None:
        worker.is_active = data.is_active
    
    db.commit()
    db.refresh(worker)
    
    log_audit_event(
        db=db,
        action='UPDATE_WORKER',
        entity_type='WORKER',
        entity_id=worker.id,
        tenant_id=tenant_id,
        user_id=user_id,
        details={'staff_code': worker.staff_code, 'is_active': worker.is_active}
    )
    return worker

def deactivate_worker(db: Session, tenant_id: str, worker_id: str, user_id: Optional[str] = None) -> Worker:
    worker = get_worker_by_id(db, tenant_id, worker_id)
    if not worker:
        raise ValueError(f"Worker '{worker_id}' not found.")
    
    worker.is_active = False
    worker.enrollment_status = 'DEACTIVATED'
    db.commit()
    db.refresh(worker)
    
    log_audit_event(
        db=db,
        action='DEACTIVATE_WORKER',
        entity_type='WORKER',
        entity_id=worker.id,
        tenant_id=tenant_id,
        user_id=user_id,
        details={'staff_code': worker.staff_code}
    )
    return worker

def enroll_worker_image(
    db: Session,
    tenant_id: str,
    worker_id: str,
    image_bytes: bytes,
    is_primary: bool = True,
    user_id: Optional[str] = None
) -> dict:
    worker = get_worker_by_id(db, tenant_id, worker_id)
    if not worker:
        raise ValueError(f"Worker '{worker_id}' not found.")
    
    nparr = np.frombuffer(image_bytes, np.uint8)
    img_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img_bgr is None:
        raise ValueError('Invalid image format or corrupted bytes.')
    
    is_ok, blur_var, quality_score = assess_image_quality(img_bgr)
    
    target_dir = os.path.join(settings.CROPS_DIR, 'enrollments', tenant_id)
    os.makedirs(target_dir, exist_ok=True)
    img_uuid = str(uuid.uuid4())
    filename = f"{worker.staff_code}_{img_uuid}.jpg"
    file_path = os.path.join(target_dir, filename)
    cv2.imwrite(file_path, img_bgr)
    
    file_hash = hashlib.sha256(image_bytes).hexdigest()
    
    if is_primary:
        stmt = select(EnrollmentImage).where(EnrollmentImage.worker_id == worker.id)
        existing_images = list(db.execute(stmt).scalars().all())
        for ei in existing_images:
            ei.is_primary = False
    
    enroll_img = EnrollmentImage(
        worker_id=worker.id,
        image_path=file_path,
        file_hash=file_hash,
        blur_score=blur_var,
        quality_score=quality_score,
        is_primary=is_primary
    )
    db.add(enroll_img)
    db.flush()
    
    engine = get_reid_engine()
    emb = engine.extract_embedding(img_bgr)
    emb_vector = [round(float(v), 6) for v in emb.tolist()]
    
    person_emb = PersonEmbedding(
        tenant_id=tenant_id,
        worker_id=worker.id,
        enrollment_image_id=enroll_img.id,
        embedding_vector=emb_vector,
        dimension=512,
        embedding_version='v1.0-onnx',
        model_version='openset_reid.onnx'
    )
    db.add(person_emb)
    
    worker.enrollment_status = 'ENROLLED'
    worker.is_active = True
    
    db.commit()
    db.refresh(enroll_img)
    db.refresh(person_emb)
    
    log_audit_event(
        db=db,
        action='ENROLL_WORKER_IMAGE',
        entity_type='WORKER',
        entity_id=worker.id,
        tenant_id=tenant_id,
        user_id=user_id,
        details={
            'image_id': enroll_img.id,
            'quality_ok': is_ok,
            'blur_score': round(blur_var, 2),
            'quality_score': round(quality_score, 4)
        }
    )
    
    return {
        'worker_id': worker.id,
        'image_id': enroll_img.id,
        'embedding_id': person_emb.id,
        'blur_score': round(blur_var, 2),
        'quality_score': round(quality_score, 4),
        'is_accepted': True,
        'quality_passed': is_ok
    }
