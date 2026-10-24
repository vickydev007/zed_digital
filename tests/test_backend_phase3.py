from __future__ import annotations
import os
import io
import time
import pytest
import numpy as np
import cv2
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from backend.core.database import Base, get_db
from backend.core.security import create_access_token, hash_password
from backend.models import (
    Tenant, User, TenantMembership, Worker, EnrollmentImage,
    PersonEmbedding, CandidateIdentity, VideoAsset, VideoJob,
    Track, Observation, MatchDecision, PassageEvent, PresenceSession,
    RepresentativeCrop, AuditLog, ExperimentRun, EvaluationResult, Camera
)
from backend.main import app
from backend.services.worker_service import create_worker, enroll_worker_image, deactivate_worker
from backend.services.candidate_service import review_candidate
from backend.schemas.worker import WorkerCreateRequest
from backend.schemas.candidate import CandidateReviewRequest
from openset_reid.pipeline.video_analyzer import (
    IdentityStatus,
    PassageStatus,
    PersonCategory,
    resolve_display_category
)

TEST_DB_URL = 'sqlite:///./data/test_phase3.db'
test_engine = create_engine(TEST_DB_URL, connect_args={'check_same_thread': False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture(scope='module', autouse=True)
def setup_test_database():
    import backend.services.job_worker as jw
    orig_session = jw.SessionLocal
    jw.SessionLocal = TestingSessionLocal
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    yield
    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=test_engine)
    jw.SessionLocal = orig_session
    if os.path.exists('./data/test_phase3.db'):
        try:
            os.remove('./data/test_phase3.db')
        except Exception:
            pass

@pytest.fixture(scope='module')
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture(scope='module')
def client():
    return TestClient(app)

@pytest.fixture(scope='module')
def seed_tenants(db_session):
    t1 = Tenant(name='Tenant Alpha', slug='tenant-alpha', is_active=True)
    t2 = Tenant(name='Tenant Beta', slug='tenant-beta', is_active=True)
    db_session.add_all([t1, t2])
    db_session.flush()

    u1 = User(
        email='alpha_admin@example.com',
        hashed_password=hash_password('Password123!'),
        full_name='Alpha Admin',
        is_superuser=False,
        is_active=True
    )
    u2 = User(
        email='beta_admin@example.com',
        hashed_password=hash_password('Password123!'),
        full_name='Beta Admin',
        is_superuser=False,
        is_active=True
    )
    u_super = User(
        email='super@example.com',
        hashed_password=hash_password('Password123!'),
        full_name='Super User',
        is_superuser=True,
        is_active=True
    )
    db_session.add_all([u1, u2, u_super])
    db_session.flush()

    m1 = TenantMembership(tenant_id=t1.id, user_id=u1.id, role='OWNER')
    m2 = TenantMembership(tenant_id=t2.id, user_id=u2.id, role='OWNER')
    db_session.add_all([m1, m2])
    db_session.commit()

    return {
        'tenant1': t1,
        'tenant2': t2,
        'user1': u1,
        'user2': u2,
        'user_super': u_super,
        'token1': create_access_token({'sub': u1.id, 'email': u1.email}),
        'token2': create_access_token({'sub': u2.id, 'email': u2.email}),
        'token_super': create_access_token({'sub': u_super.id, 'email': u_super.email})
    }

def test_database_model_creation(db_session):
    tables = Base.metadata.tables.keys()
    required = [
        'tenants', 'users', 'tenant_memberships', 'cameras', 'camera_credentials',
        'workers', 'enrollment_images', 'person_embeddings', 'candidate_identities',
        'video_assets', 'video_jobs', 'tracks', 'observations', 'match_decisions',
        'passage_events', 'presence_sessions', 'representative_crops', 'audit_logs',
        'experiment_runs', 'evaluation_results'
    ]
    for r in required:
        assert r in tables

def test_tenant_isolation_cross_tenant_rejection(client, seed_tenants):
    headers1 = {
        'Authorization': f"Bearer {seed_tenants['token1']}",
        'X-Tenant-ID': seed_tenants['tenant1'].id
    }
    resp1 = client.post(
        '/api/v1/workers',
        json={'staff_code': 'W_ALPHA_01', 'full_name': 'Worker Alpha'},
        headers=headers1
    )
    assert resp1.status_code == 201
    worker_alpha_id = resp1.json()['id']

    headers2_wrong_tenant = {
        'Authorization': f"Bearer {seed_tenants['token2']}",
        'X-Tenant-ID': seed_tenants['tenant1'].id
    }
    resp2 = client.get('/api/v1/workers', headers=headers2_wrong_tenant)
    assert resp2.status_code == 403
    assert 'Cross-tenant access forbidden' in resp2.json()['detail']

    headers2_own_tenant = {
        'Authorization': f"Bearer {seed_tenants['token2']}",
        'X-Tenant-ID': seed_tenants['tenant2'].id
    }
    resp3 = client.get(f"/api/v1/workers/{worker_alpha_id}", headers=headers2_own_tenant)
    assert resp3.status_code == 404

def test_worker_enrollment_and_deactivation(db_session, seed_tenants):
    tenant = seed_tenants['tenant1']
    data = WorkerCreateRequest(
        staff_code='W_TEST_ENROLL',
        full_name='Test Enrollment Worker',
        department='Security',
        uniform_category='Navy Uniform'
    )
    worker = create_worker(db_session, tenant.id, data)
    assert worker.enrollment_status == 'PENDING_REVIEW'

    dummy_crop = np.full((128, 64, 3), 180, dtype=np.uint8)
    for y in range(0, 128, 8):
        dummy_crop[y:y+4, :] = 30
    _, img_bytes = cv2.imencode('.jpg', dummy_crop)

    res = enroll_worker_image(
        db=db_session,
        tenant_id=tenant.id,
        worker_id=worker.id,
        image_bytes=img_bytes.tobytes()
    )
    assert res['is_accepted'] is True
    assert res['quality_passed'] is True
    assert worker.enrollment_status == 'ENROLLED'

    emb_stmt = select(PersonEmbedding).where(PersonEmbedding.worker_id == worker.id)
    embs = list(db_session.execute(emb_stmt).scalars().all())
    assert len(embs) == 1
    assert embs[0].dimension == 512
    assert len(embs[0].embedding_vector) == 512

    deactivated = deactivate_worker(db_session, tenant.id, worker.id)
    assert deactivated.is_active is False
    assert deactivated.enrollment_status == 'DEACTIVATED'

def test_candidate_identity_lifecycle_and_review(db_session, seed_tenants):
    tenant = seed_tenants['tenant1']
    cand = CandidateIdentity(
        tenant_id=tenant.id,
        candidate_code='CAND_TEST_999',
        review_status='PROVISIONAL',
        notes='Provisional unknown cluster'
    )
    db_session.add(cand)
    db_session.commit()
    db_session.refresh(cand)

    assert cand.review_status == 'PROVISIONAL'

    review_data = CandidateReviewRequest(
        review_status='APPROVED',
        notes='Reviewed and promoted to approved visitor'
    )
    reviewed = review_candidate(db_session, tenant.id, cand.id, review_data)
    assert reviewed.review_status == 'APPROVED'
    assert 'promoted' in reviewed.notes

def test_status_decoupling_and_four_color_categories():
    cat1 = resolve_display_category(IdentityStatus.OFFICIAL_WORKER, PassageStatus.FIRST_ENTRY)
    assert cat1 == PersonCategory.OFFICIAL_WORKER

    cat2 = resolve_display_category(IdentityStatus.OFFICIAL_WORKER, PassageStatus.REPEAT_PASSAGE)
    assert cat2 == PersonCategory.PREVIOUSLY_ENROLLED

    cat3 = resolve_display_category(IdentityStatus.NEW_CANDIDATE, PassageStatus.FIRST_ENTRY)
    assert cat3 == PersonCategory.NEW_PERSON

    cat4 = resolve_display_category(IdentityStatus.UNKNOWN, PassageStatus.FIRST_ENTRY)
    assert cat4 == PersonCategory.UNKNOWN

    cat5 = resolve_display_category(IdentityStatus.NEW_CANDIDATE, PassageStatus.REPEAT_PASSAGE)
    assert cat5 == PersonCategory.PREVIOUSLY_ENROLLED

def test_camera_management_and_credential_protection(client, seed_tenants):
    headers = {
        'Authorization': f"Bearer {seed_tenants['token1']}",
        'X-Tenant-ID': seed_tenants['tenant1'].id
    }
    create_payload = {
        'name': 'North Gate CCTV',
        'location': 'Gate 1',
        'rtsp_url': 'rtsp://admin:super_secret_pass@192.168.1.50:554/stream',
        'stream_fps': 25.0
    }
    resp = client.post('/api/v1/cameras', json=create_payload, headers=headers)
    assert resp.status_code == 201
    cam_data = resp.json()
    assert cam_data['name'] == 'North Gate CCTV'
    assert cam_data['has_encrypted_stream'] is True
    assert 'super_secret_pass' not in str(cam_data)

    cam_id = cam_data['id']
    start_resp = client.post(f"/api/v1/cameras/{cam_id}/start", headers=headers)
    assert start_resp.status_code == 200
    assert start_resp.json()['status'] == 'ONLINE'

    stop_resp = client.post(f"/api/v1/cameras/{cam_id}/stop", headers=headers)
    assert stop_resp.status_code == 200
    assert stop_resp.json()['status'] == 'OFFLINE'

def test_video_upload_and_job_execution(client, seed_tenants, db_session):
    headers = {
        'Authorization': f"Bearer {seed_tenants['token1']}",
        'X-Tenant-ID': seed_tenants['tenant1'].id
    }

    test_video_path = os.path.join('data', 'test_synthetic.mp4')
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(test_video_path, fourcc, 10.0, (160, 120))
    for i in range(15):
        frame = np.full((120, 160, 3), 40, dtype=np.uint8)
        cv2.rectangle(frame, (50, 30), (90, 110), (120, 150, 200), -1)
        out.write(frame)
    out.release()

    with open(test_video_path, 'rb') as f:
        resp = client.post(
            '/api/v1/videos/upload',
            files={'file': ('synthetic.mp4', f, 'video/mp4')},
            headers=headers
        )
    assert resp.status_code == 201
    video_id = resp.json()['id']
    assert resp.json()['validation_status'] == 'VALIDATED'

    analyze_resp = client.post(
        f"/api/v1/videos/{video_id}/analyze",
        json={'score_threshold': 0.7124, 'contrast_margin': 0.05, 'max_frames': 10},
        headers=headers
    )
    assert analyze_resp.status_code == 202
    job_id = analyze_resp.json()['id']
    assert analyze_resp.json()['status'] in ('QUEUED', 'RUNNING')

    time.sleep(1.5)

    status_resp = client.get(f"/api/v1/jobs/{job_id}", headers=headers)
    assert status_resp.status_code == 200
    job_status = status_resp.json()['status']
    assert job_status in ('QUEUED', 'RUNNING', 'COMPLETED')

    if os.path.exists(test_video_path):
        os.remove(test_video_path)

def test_dashboard_stats_and_empirical_benchmarks(client, seed_tenants):
    headers = {
        'Authorization': f"Bearer {seed_tenants['token1']}",
        'X-Tenant-ID': seed_tenants['tenant1'].id
    }
    resp = client.get('/api/v1/dashboard/stats', headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert 'active_workers_present' in data
    assert 'category_counts' in data
    assert 'OFFICIAL_WORKER' in data['category_counts']
    assert 'PREVIOUSLY_ENROLLED' in data['category_counts']

    bench_resp = client.get('/api/v1/evaluation/benchmarks')
    assert bench_resp.status_code == 200
    bdata = bench_resp.json()
    assert bdata['status'] == 'EMPIRICALLY_VERIFIED'
    metrics = bdata['metrics']
    assert abs(metrics['actual_far'] - 0.2023) < 0.005
    assert abs(metrics['genuine_recall_tar'] - 0.9448) < 0.005
    assert abs(metrics['impostor_rejection_rate'] - 0.7977) < 0.005
