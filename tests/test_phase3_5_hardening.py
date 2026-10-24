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
    Track, PassageEvent, RepresentativeCrop, Camera
)
from backend.main import app
from backend.services.job_worker import recover_orphaned_jobs, _persist_analysis_results
from openset_reid.pipeline.video_analyzer import (
    IdentityStatus,
    PassageStatus,
    PersonCategory,
    resolve_display_category
)

TEST_DB_URL = 'sqlite:///./data/test_phase3_5.db'
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
    if os.path.exists('./data/test_phase3_5.db'):
        try:
            os.remove('./data/test_phase3_5.db')
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
def test_setup_data(db_session):
    t_alpha = Tenant(name='Facility Alpha', slug='facility-alpha', is_active=True)
    t_beta = Tenant(name='Facility Beta', slug='facility-beta', is_active=True)
    db_session.add_all([t_alpha, t_beta])
    db_session.flush()

    u_owner = User(
        email='owner_alpha@test.com',
        hashed_password=hash_password('Pass1234!'),
        full_name='Alpha Owner',
        is_superuser=False,
        is_active=True
    )
    u_viewer = User(
        email='viewer_alpha@test.com',
        hashed_password=hash_password('Pass1234!'),
        full_name='Alpha Viewer',
        is_superuser=False,
        is_active=True
    )
    u_beta = User(
        email='owner_beta@test.com',
        hashed_password=hash_password('Pass1234!'),
        full_name='Beta Owner',
        is_superuser=False,
        is_active=True
    )
    db_session.add_all([u_owner, u_viewer, u_beta])
    db_session.flush()

    m_owner = TenantMembership(tenant_id=t_alpha.id, user_id=u_owner.id, role='OWNER')
    m_viewer = TenantMembership(tenant_id=t_alpha.id, user_id=u_viewer.id, role='VIEWER')
    m_beta = TenantMembership(tenant_id=t_beta.id, user_id=u_beta.id, role='OWNER')
    db_session.add_all([m_owner, m_viewer, m_beta])
    db_session.flush()

    w_beta = Worker(
        tenant_id=t_beta.id,
        staff_code='W_BETA_CONFIDENTIAL',
        full_name='Secret Beta Worker',
        enrollment_status='ENROLLED'
    )
    db_session.add(w_beta)
    db_session.flush()

    c_beta = Camera(
        tenant_id=t_beta.id,
        name='Beta Vault Camera',
        location='Vault 1',
        is_active=True,
        status='ONLINE'
    )
    db_session.add(c_beta)
    db_session.flush()

    v_beta = VideoAsset(
        tenant_id=t_beta.id,
        original_filename='beta_vault.mp4',
        stored_path='data/uploads/beta/sample.mp4',
        validation_status='VALIDATED'
    )
    db_session.add(v_beta)
    db_session.flush()

    crop_beta = RepresentativeCrop(
        tenant_id=t_beta.id,
        file_path='data/crops/beta_sample.jpg',
        retention_status='RETAINED'
    )
    db_session.add(crop_beta)
    db_session.commit()

    return {
        'tenant_alpha': t_alpha,
        'tenant_beta': t_beta,
        'token_owner': create_access_token({'sub': u_owner.id, 'email': u_owner.email}),
        'token_viewer': create_access_token({'sub': u_viewer.id, 'email': u_viewer.email}),
        'token_beta': create_access_token({'sub': u_beta.id, 'email': u_beta.email}),
        'worker_beta_id': w_beta.id,
        'camera_beta_id': c_beta.id,
        'video_beta_id': v_beta.id,
        'crop_beta_id': crop_beta.id
    }

def test_ssrf_camera_url_validation_rejection(client, test_setup_data):
    headers = {
        'Authorization': f"Bearer {test_setup_data['token_owner']}",
        'X-Tenant-ID': test_setup_data['tenant_alpha'].id
    }
    forbidden_urls = [
        'rtsp://localhost:554/stream',
        'rtsp://127.0.0.1:8554/live',
        'http://169.254.169.254/latest/meta-data',
        'file:///etc/passwd',
        'gopher://127.0.0.1:70',
        'ftp://192.168.1.1:21'
    ]
    for bad_url in forbidden_urls:
        resp = client.post(
            '/api/v1/cameras',
            json={'name': 'SSRF Attempt', 'rtsp_url': bad_url},
            headers=headers
        )
        assert resp.status_code == 400
        assert 'Forbidden' in resp.json()['detail'] or 'Unsupported stream scheme' in resp.json()['detail']

def test_cross_tenant_access_rejection(client, test_setup_data):
    headers_alpha = {
        'Authorization': f"Bearer {test_setup_data['token_owner']}",
        'X-Tenant-ID': test_setup_data['tenant_alpha'].id
    }

    w_id = test_setup_data['worker_beta_id']
    resp_w = client.get(f"/api/v1/workers/{w_id}", headers=headers_alpha)
    assert resp_w.status_code == 404

    c_id = test_setup_data['camera_beta_id']
    resp_c = client.get(f"/api/v1/cameras/{c_id}", headers=headers_alpha)
    assert resp_c.status_code == 404

    v_id = test_setup_data['video_beta_id']
    resp_v = client.get(f"/api/v1/videos/{v_id}", headers=headers_alpha)
    assert resp_v.status_code == 404

    crop_id = test_setup_data['crop_beta_id']
    resp_crop = client.get(f"/api/v1/media/crops/{crop_id}", headers=headers_alpha)
    assert resp_crop.status_code == 404

def test_role_based_access_control(client, test_setup_data):
    headers_viewer = {
        'Authorization': f"Bearer {test_setup_data['token_viewer']}",
        'X-Tenant-ID': test_setup_data['tenant_alpha'].id
    }

    resp_get = client.get('/api/v1/workers', headers=headers_viewer)
    assert resp_get.status_code == 200

    resp_post_worker = client.post(
        '/api/v1/workers',
        json={'staff_code': 'W_VIEWER_DENIED', 'full_name': 'Should Fail'},
        headers=headers_viewer
    )
    assert resp_post_worker.status_code == 403
    assert 'Insufficient permissions' in resp_post_worker.json()['detail']

    resp_post_camera = client.post(
        '/api/v1/cameras',
        json={'name': 'Viewer Camera'},
        headers=headers_viewer
    )
    assert resp_post_camera.status_code == 403

def test_video_upload_validation_size_and_format(client, test_setup_data):
    headers = {
        'Authorization': f"Bearer {test_setup_data['token_owner']}",
        'X-Tenant-ID': test_setup_data['tenant_alpha'].id
    }

    resp_empty = client.post(
        '/api/v1/videos/upload',
        files={'file': ('empty.mp4', b'tiny', 'video/mp4')},
        headers=headers
    )
    assert resp_empty.status_code == 400
    assert 'empty or too small' in resp_empty.json()['detail']

    resp_bad_ext = client.post(
        '/api/v1/videos/upload',
        files={'file': ('payload.exe', b'A' * 500, 'application/octet-stream')},
        headers=headers
    )
    assert resp_bad_ext.status_code == 400
    assert 'Unsupported video format' in resp_bad_ext.json()['detail']

def test_job_orphan_recovery_after_restart(db_session, test_setup_data):
    tenant = test_setup_data['tenant_alpha']
    asset = VideoAsset(
        tenant_id=tenant.id,
        original_filename='orphan_test.mp4',
        stored_path='data/uploads/orphan_test.mp4',
        validation_status='VALIDATED'
    )
    db_session.add(asset)
    db_session.flush()

    orphan_job1 = VideoJob(
        tenant_id=tenant.id,
        video_asset_id=asset.id,
        status='RUNNING',
        progress_percent=45.0
    )
    orphan_job2 = VideoJob(
        tenant_id=tenant.id,
        video_asset_id=asset.id,
        status='QUEUED',
        progress_percent=0.0
    )
    db_session.add_all([orphan_job1, orphan_job2])
    db_session.commit()

    recovered_count = recover_orphaned_jobs(db_session)
    assert recovered_count >= 2

    db_session.refresh(orphan_job1)
    db_session.refresh(orphan_job2)
    assert orphan_job1.status == 'FAILED'
    assert 'recovered on startup' in orphan_job1.error_details
    assert orphan_job2.status == 'FAILED'

def test_job_retry_idempotency(db_session, test_setup_data):
    tenant = test_setup_data['tenant_alpha']
    asset = VideoAsset(
        tenant_id=tenant.id,
        original_filename='retry_idempotent.mp4',
        stored_path='data/uploads/retry_idempotent.mp4',
        validation_status='VALIDATED'
    )
    db_session.add(asset)
    db_session.flush()

    job = VideoJob(
        tenant_id=tenant.id,
        video_asset_id=asset.id,
        status='RUNNING'
    )
    db_session.add(job)
    db_session.commit()

    mock_summary = {
        'threshold_tau': 0.7124,
        'contrast_margin': 0.05,
        'tracks': [
            {
                'track_id': 1,
                'identity_status': 'OFFICIAL_WORKER',
                'passage_status': 'FIRST_ENTRY',
                'display_category': 'OFFICIAL_WORKER',
                'matched_identity': None,
                'best_score': 0.88,
                'runner_up_score': 0.70,
                'score_margin': 0.18,
                'first_frame': 1,
                'last_frame': 15,
                'seen_frames': 15,
                'crop_file': None
            },
            {
                'track_id': 2,
                'identity_status': 'NEW_CANDIDATE',
                'candidate_id': 101,
                'passage_status': 'FIRST_ENTRY',
                'display_category': 'NEW_PERSON',
                'matched_identity': None,
                'best_score': 0.65,
                'runner_up_score': 0.62,
                'score_margin': 0.03,
                'first_frame': 5,
                'last_frame': 20,
                'seen_frames': 15,
                'crop_file': None
            }
        ]
    }

    _persist_analysis_results(job.id, tenant.id, mock_summary)
    t_cnt1 = db_session.query(Track).filter_by(video_job_id=job.id).count()
    e_cnt1 = db_session.query(PassageEvent).filter_by(video_job_id=job.id).count()
    assert t_cnt1 == 2
    assert e_cnt1 == 2

    _persist_analysis_results(job.id, tenant.id, mock_summary)
    t_cnt2 = db_session.query(Track).filter_by(video_job_id=job.id).count()
    e_cnt2 = db_session.query(PassageEvent).filter_by(video_job_id=job.id).count()
    assert t_cnt2 == 2
    assert e_cnt2 == 2

def test_identity_and_passage_semantics_repeat_worker():
    cat_first = resolve_display_category(IdentityStatus.OFFICIAL_WORKER, PassageStatus.FIRST_ENTRY)
    assert cat_first == PersonCategory.OFFICIAL_WORKER

    cat_repeat = resolve_display_category(IdentityStatus.OFFICIAL_WORKER, PassageStatus.REPEAT_PASSAGE)
    assert cat_repeat == PersonCategory.PREVIOUSLY_ENROLLED

    cat_cand_repeat = resolve_display_category(IdentityStatus.NEW_CANDIDATE, PassageStatus.REPEAT_PASSAGE)
    assert cat_cand_repeat == PersonCategory.PREVIOUSLY_ENROLLED

    cat_cand_first = resolve_display_category(IdentityStatus.NEW_CANDIDATE, PassageStatus.FIRST_ENTRY)
    assert cat_cand_first == PersonCategory.NEW_PERSON

    cat_unknown = resolve_display_category(IdentityStatus.UNKNOWN, PassageStatus.FIRST_ENTRY)
    assert cat_unknown == PersonCategory.UNKNOWN
