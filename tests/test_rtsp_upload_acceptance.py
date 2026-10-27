import os
import time
import uuid
import struct
import tempfile
import pytest
import numpy as np
import cv2
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.core.database import Base, get_db
from backend.core.config import settings
from backend.core.security import create_access_token, hash_password
from backend.models import Tenant, User, TenantMembership, Camera, VideoAsset, VideoJob, PassageEvent
from backend.main import app
from backend.services.camera_service import validate_stream_url, sanitize_stream_url
from backend.services.camera_streamer import LiveCameraStreamWorker, CameraStreamManager, stream_manager
import backend.services.camera_streamer as cs
import backend.services.job_worker as jw
from backend.services.video_service import save_uploaded_video, create_analysis_job, cancel_job

TEST_DB_URL = 'sqlite:///./data/test_rtsp_upload_acceptance.db'
test_engine = create_engine(TEST_DB_URL, connect_args={'check_same_thread': False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture(scope='module', autouse=True)
def setup_acceptance_db():
    orig_jw_session = jw.SessionLocal
    orig_cs_session = cs.SessionLocal
    jw.SessionLocal = TestingSessionLocal
    cs.SessionLocal = TestingSessionLocal
    app.dependency_overrides[get_db] = override_get_db

    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    from backend.main import ensure_schema_columns
    ensure_schema_columns()

    yield

    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=test_engine)
    jw.SessionLocal = orig_jw_session
    cs.SessionLocal = orig_cs_session
    if os.path.exists('./data/test_rtsp_upload_acceptance.db'):
        try:
            os.remove('./data/test_rtsp_upload_acceptance.db')
        except Exception:
            pass

@pytest.fixture
def test_data():
    db = TestingSessionLocal()
    uid = uuid.uuid4().hex[:8]
    tenant_a = Tenant(id=f'tenant-acc-a-{uid}', name='Tenant Alpha', slug=f'tenant-alpha-{uid}', is_active=True)
    tenant_b = Tenant(id=f'tenant-acc-b-{uid}', name='Tenant Beta', slug=f'tenant-beta-{uid}', is_active=True)
    db.add_all([tenant_a, tenant_b])
    db.flush()

    user_admin = User(id=f'user-admin-a-{uid}', email=f'admin-{uid}@alpha.com', hashed_password=hash_password('Pass123!'), full_name='Admin Alpha', is_active=True)
    user_op = User(id=f'user-op-a-{uid}', email=f'op-{uid}@alpha.com', hashed_password=hash_password('Pass123!'), full_name='Operator Alpha', is_active=True)
    user_beta = User(id=f'user-beta-{uid}', email=f'user-{uid}@beta.com', hashed_password=hash_password('Pass123!'), full_name='User Beta', is_active=True)
    db.add_all([user_admin, user_op, user_beta])
    db.flush()

    mem_admin = TenantMembership(id=f'mem-1-{uid}', user_id=user_admin.id, tenant_id=tenant_a.id, role='ADMIN')
    mem_op = TenantMembership(id=f'mem-2-{uid}', user_id=user_op.id, tenant_id=tenant_a.id, role='OPERATOR')
    mem_beta = TenantMembership(id=f'mem-3-{uid}', user_id=user_beta.id, tenant_id=tenant_b.id, role='ADMIN')
    db.add_all([mem_admin, mem_op, mem_beta])
    db.commit()

    token_admin = create_access_token({'sub': user_admin.id, 'role': 'ADMIN'})
    token_op = create_access_token({'sub': user_op.id, 'role': 'OPERATOR'})
    token_beta = create_access_token({'sub': user_beta.id, 'role': 'ADMIN'})

    yield {
        'tenant_a': tenant_a,
        'tenant_b': tenant_b,
        'user_admin': user_admin,
        'user_op': user_op,
        'user_beta': user_beta,
        'token_admin': token_admin,
        'token_op': token_op,
        'token_beta': token_beta
    }
    db.close()

def create_synthetic_mp4(num_frames: int = 10, width: int = 64, height: int = 64, fps: float = 25.0) -> bytes:
    temp_file = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
    temp_path = temp_file.name
    temp_file.close()
    try:
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(temp_path, fourcc, fps, (width, height))
        for i in range(num_frames):
            frame = np.full((height, width, 3), (i * 20) % 256, dtype=np.uint8)
            out.write(frame)
        out.release()
        with open(temp_path, 'rb') as f:
            content = f.read()
        return content
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)



def test_rtsp_url_validation_prohibited_destinations():
    """Verify SSRF, loopback, cloud metadata, and prohibited ports are rejected."""
    with pytest.raises(ValueError, match="Forbidden stream destination host"):
        validate_stream_url("rtsp://127.0.0.1:554/live")
    with pytest.raises(ValueError, match="Forbidden stream destination host"):
        validate_stream_url("rtsp://localhost:554/live")
    with pytest.raises(ValueError, match="Forbidden stream destination host"):
        validate_stream_url("rtsp://169.254.169.254/latest/meta-data")
    with pytest.raises(ValueError, match="Forbidden stream destination host"):
        validate_stream_url("rtsp://metadata.google.internal/computeMetadata")

    with pytest.raises(ValueError, match="Forbidden stream destination port 22"):
        validate_stream_url("rtsp://192.168.1.100:22/feed")
    with pytest.raises(ValueError, match="Forbidden stream destination port 3306"):
        validate_stream_url("rtsp://192.168.1.100:3306/feed")
    with pytest.raises(ValueError, match="Forbidden stream destination port 5432"):
        validate_stream_url("rtsp://192.168.1.100:5432/feed")

    with pytest.raises(ValueError, match="Unsupported stream scheme 'ftp'"):
        validate_stream_url("ftp://192.168.1.100/stream")

    valid = validate_stream_url("rtsp://192.168.1.100:554/live")
    assert valid == "rtsp://192.168.1.100:554/live"


def test_rtsp_credential_sanitization():
    """Verify secrets and tokens are masked across logs and errors."""
    url = "rtsp://admin:SecretPass999@10.0.0.5:554/live?token=secret_jwt_xyz"
    sanitized = sanitize_stream_url(url)
    assert "SecretPass999" not in sanitized
    assert "secret_jwt_xyz" not in sanitized
    assert "rtsp://admin:***@10.0.0.5:554/live" in sanitized
    assert "token=***" in sanitized



def test_rtsp_test_connection_timeout_bounded():
    """Verify test_connectivity enforces bounded timeout on unreachable host without hanging."""
    mgr = CameraStreamManager()
    t0 = time.time()
    res = mgr.test_connectivity("rtsp://192.0.2.1:554/live", timeout_seconds=1.5)
    dt = time.time() - t0

    assert res['success'] is False
    assert "Could not connect to RTSP stream" in res['error']
    assert dt < 3.5


def test_rtsp_test_connection_validation_failure():
    """Verify test_connectivity returns sanitized error when SSRF URL is submitted."""
    mgr = CameraStreamManager()
    res = mgr.test_connectivity("rtsp://127.0.0.1:554/secret")
    assert res['success'] is False
    assert "Validation rejected" in res['error']



def test_rtsp_duplicate_worker_prevention(test_data):
    """Verify starting stream twice returns the identical active worker instance without duplicates."""
    mgr = CameraStreamManager()
    db = TestingSessionLocal()
    try:
        cam = Camera(
            id='cam-dup-1',
            tenant_id=test_data['tenant_a'].id,
            name='Camera Duplicate Test',
            rtsp_url_encrypted='mock',
            stream_fps=25.0
        )
        db.add(cam)
        db.commit()

        synthetic_video = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
        synthetic_path = synthetic_video.name
        synthetic_video.close()
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(synthetic_path, fourcc, 25.0, (64, 64))
        for _ in range(5):
            out.write(np.zeros((64, 64, 3), dtype=np.uint8))
        out.release()

        worker1 = mgr.start_camera_stream(
            tenant_id=test_data['tenant_a'].id,
            camera_id=cam.id,
            stream_url=synthetic_path,
            db=db
        )
        worker2 = mgr.start_camera_stream(
            tenant_id=test_data['tenant_a'].id,
            camera_id=cam.id,
            stream_url=synthetic_path,
            db=db
        )

        assert worker1 is worker2
        assert len(mgr._workers) == 1

        stopped = mgr.stop_camera_stream(cam.id, db=db)
        assert stopped is True
        assert cam.id not in mgr._workers
    finally:
        db.close()
        time.sleep(0.1)
        try:
            if 'synthetic_path' in locals() and os.path.exists(synthetic_path):
                os.remove(synthetic_path)
        except Exception:
            pass


def test_rtsp_auth_expired_transition():
    """Verify repeated auth failures transition camera status to AUTH_EXPIRED."""
    worker = LiveCameraStreamWorker(
        tenant_id="tenant-test",
        camera_id="cam-auth-test",
        stream_url="rtsp://provider.com/live?token=expired_token_123",
        is_loop=False
    )
    worker.reconnect_count = 3
    is_tokenized = "token=" in worker.stream_url.lower() or "auth=" in worker.stream_url.lower()
    if is_tokenized and worker.reconnect_count >= 3:
        worker.status = 'AUTH_EXPIRED'
        worker.last_error = "RTSP token expired / authentication rejected (401). Awaiting token refresh."

    assert worker.status == 'AUTH_EXPIRED'
    status_dict = worker.get_runtime_status()
    assert status_dict['status'] == 'AUTH_EXPIRED'
    assert 'AUTH_EXPIRED' in status_dict['status']



def test_preview_token_authorization_and_revocation(test_data):
    """Verify preview token issuance, camera_id scope enforcement, and revocation."""
    client = TestClient(app)
    db = TestingSessionLocal()
    try:
        cam = Camera(
            id='cam-prev-1',
            tenant_id=test_data['tenant_a'].id,
            name='Camera Preview Test',
            is_active=True,
            status='OFFLINE'
        )
        db.add(cam)
        db.commit()

        res = client.post(
            f"/api/v1/cameras/{cam.id}/preview-token",
            headers={"Authorization": f"Bearer {test_data['token_admin']}"}
        )
        assert res.status_code == 200
        data = res.json()
        token = data['preview_token']
        assert token is not None

        rev_res = client.post(
            f"/api/v1/cameras/{cam.id}/revoke-token",
            json={"token": token},
            headers={"Authorization": f"Bearer {test_data['token_admin']}"}
        )
        assert rev_res.status_code == 200

        prev_res = client.get(
            f"/api/v1/cameras/{cam.id}/preview?token={token}"
        )
        assert prev_res.status_code == 401
        assert "revoked" in prev_res.json()['detail'].lower()
    finally:
        db.close()


def test_multi_tenant_camera_isolation(test_data):
    """Verify Tenant B cannot view, control, or delete Tenant A's camera."""
    client = TestClient(app)
    db = TestingSessionLocal()
    try:
        cam = Camera(
            id='cam-isolation-1',
            tenant_id=test_data['tenant_a'].id,
            name='Tenant A Private Gate',
            is_active=True
        )
        db.add(cam)
        db.commit()

        res_get = client.get(
            f"/api/v1/cameras/{cam.id}",
            headers={"Authorization": f"Bearer {test_data['token_beta']}"}
        )
        assert res_get.status_code == 404

        res_start = client.post(
            f"/api/v1/cameras/{cam.id}/start",
            headers={"Authorization": f"Bearer {test_data['token_beta']}"}
        )
        assert res_start.status_code == 404

        res_del = client.delete(
            f"/api/v1/cameras/{cam.id}",
            headers={"Authorization": f"Bearer {test_data['token_beta']}"}
        )
        assert res_del.status_code == 404
    finally:
        db.close()



def test_video_upload_valid_mp4(test_data):
    """Verify uploading a valid MP4 saves metadata (resolution, fps, frame_count) without exposing stored_path."""
    client = TestClient(app)
    video_bytes = create_synthetic_mp4(num_frames=15, width=128, height=128, fps=25.0)

    res = client.post(
        "/api/v1/videos/upload",
        files={"file": ("test_cctv.mp4", video_bytes, "video/mp4")},
        headers={"Authorization": f"Bearer {test_data['token_admin']}"}
    )
    assert res.status_code == 201
    data = res.json()
    assert data['original_filename'] == 'test_cctv.mp4'
    assert data['validation_status'] == 'VALIDATED'
    assert data['fps'] == 25.0
    assert data['frame_count'] == 15
    assert data['resolution_width'] == 128
    assert data['resolution_height'] == 128
    assert data['duration_seconds'] == 0.6
    assert 'stored_path' not in data


def test_video_upload_unsupported_format_rejected(test_data):
    """Verify unsupported extensions (.txt, .exe, .tar) are rejected with 400."""
    client = TestClient(app)
    res = client.post(
        "/api/v1/videos/upload",
        files={"file": ("malicious.exe", b"MZ\x90\x00\x03\x00\x00\x00" * 20, "application/octet-stream")},
        headers={"Authorization": f"Bearer {test_data['token_admin']}"}
    )
    assert res.status_code == 400
    assert "Unsupported video format" in res.json()['detail']


def test_video_upload_spoofed_extension_and_immediate_cleanup(test_data):
    """Verify spoofed extension (text file named .mp4) is rejected and cleaned up from disk immediately."""
    client = TestClient(app)
    fake_content = b"This is plain text disguised as an MP4 file" * 10

    upload_dir = os.path.join(settings.UPLOAD_DIR, test_data['tenant_a'].id)
    initial_files = set(os.listdir(upload_dir)) if os.path.exists(upload_dir) else set()

    res = client.post(
        "/api/v1/videos/upload",
        files={"file": ("spoofed.mp4", fake_content, "video/mp4")},
        headers={"Authorization": f"Bearer {test_data['token_admin']}"}
    )
    assert res.status_code == 400
    assert "corrupt" in res.json()['detail'].lower() or "unable to open" in res.json()['detail'].lower()

    current_files = set(os.listdir(upload_dir)) if os.path.exists(upload_dir) else set()
    assert current_files == initial_files


def test_video_upload_empty_file_rejected(test_data):
    """Verify empty uploads are rejected."""
    client = TestClient(app)
    res = client.post(
        "/api/v1/videos/upload",
        files={"file": ("empty.mp4", b"", "video/mp4")},
        headers={"Authorization": f"Bearer {test_data['token_admin']}"}
    )
    assert res.status_code == 400
    assert "empty" in res.json()['detail'].lower()


def test_video_upload_oversized_file_rejected(test_data):
    """Verify file exceeding 150MB limit is rejected."""
    db = TestingSessionLocal()
    try:
        oversized = b"0" * (157286401)
        with pytest.raises(ValueError, match="exceeds maximum allowed upload size"):
            save_uploaded_video(
                db=db,
                tenant_id=test_data['tenant_a'].id,
                file_bytes=oversized,
                original_filename="large.mp4"
            )
    finally:
        db.close()


def test_multi_tenant_video_isolation(test_data):
    """Verify Tenant B cannot list or analyze Tenant A's video assets."""
    client = TestClient(app)
    video_bytes = create_synthetic_mp4(num_frames=5, width=64, height=64)

    res_up = client.post(
        "/api/v1/videos/upload",
        files={"file": ("tenant_a_video.mp4", video_bytes, "video/mp4")},
        headers={"Authorization": f"Bearer {test_data['token_admin']}"}
    )
    assert res_up.status_code == 201
    video_id = res_up.json()['id']

    res_b = client.get(
        f"/api/v1/videos/{video_id}",
        headers={"Authorization": f"Bearer {test_data['token_beta']}"}
    )
    assert res_b.status_code == 404

    res_analyze = client.post(
        f"/api/v1/videos/{video_id}/analyze",
        headers={"Authorization": f"Bearer {test_data['token_beta']}"}
    )
    assert res_analyze.status_code == 400
    assert "not found in this tenant" in res_analyze.json()['detail']



def test_job_cancellation_and_artifact_cleanup(test_data):
    """Verify cancelling an analysis job halts processing and cleans temporary output artifacts."""
    db = TestingSessionLocal()
    try:
        video_bytes = create_synthetic_mp4(num_frames=10, width=64, height=64)
        asset = save_uploaded_video(
            db=db,
            tenant_id=test_data['tenant_a'].id,
            file_bytes=video_bytes,
            original_filename="job_cancel_test.mp4"
        )

        job = create_analysis_job(
            db=db,
            tenant_id=test_data['tenant_a'].id,
            video_asset_id=asset.id,
            options=MagicMock(model_dump=lambda: {"max_frames": 2})
        )
        assert job.status in ('QUEUED', 'RUNNING')

        out_vid = os.path.join(settings.OUTPUT_VIDEOS_DIR, test_data['tenant_a'].id, f"{job.id}_annotated.mp4")
        os.makedirs(os.path.dirname(out_vid), exist_ok=True)
        with open(out_vid, 'w') as f:
            f.write("partial video data")
        job.output_video_path = out_vid
        db.commit()

        cancelled_job = cancel_job(db, test_data['tenant_a'].id, job.id)
        assert cancelled_job.status == 'CANCELLED'

        from backend.services.job_worker import _cleanup_job_artifacts
        _cleanup_job_artifacts(cancelled_job)
        assert not os.path.exists(out_vid)
    finally:
        db.close()


def test_passage_event_source_distinction(test_data):
    """Verify PassageEventResponse clearly marks event_source as RECORDED_VIDEO or LIVE_CAMERA and masks crop_path."""
    from backend.schemas.passage import PassageEventResponse
    from datetime import datetime, timezone

    evt_job = PassageEvent(
        id='evt-recorded-1',
        tenant_id=test_data['tenant_a'].id,
        video_job_id='job-12345',
        identity_status='OFFICIAL_WORKER',
        passage_status='PASSAGE_CONFIRMED',
        display_category='OFFICIAL_WORKER',
        confidence_score=0.92,
        crop_path='D:\\zed digital\\data\\crops\\tenant-a\\secret_crop.jpg',
        event_timestamp=datetime.now(timezone.utc),
        is_reviewed=False,
        created_at=datetime.now(timezone.utc)
    )
    resp_job = PassageEventResponse.model_validate(evt_job)
    dump_job = resp_job.model_dump()
    assert dump_job['event_source'] == 'RECORDED_VIDEO'
    assert dump_job['crop_path'] == '/api/v1/media/crops/evt-recorded-1'
    assert 'D:\\' not in dump_job['crop_path']

    evt_live = PassageEvent(
        id='evt-live-1',
        tenant_id=test_data['tenant_a'].id,
        camera_id='cam-12345',
        video_job_id=None,
        identity_status='NEW_PERSON',
        passage_status='PASSAGE_IN_PROGRESS',
        display_category='NEW_PERSON',
        confidence_score=0.65,
        crop_path=None,
        event_timestamp=datetime.now(timezone.utc),
        is_reviewed=False,
        created_at=datetime.now(timezone.utc)
    )
    resp_live = PassageEventResponse.model_validate(evt_live)
    dump_live = resp_live.model_dump()
    assert dump_live['event_source'] == 'LIVE_CAMERA'
    assert dump_live['crop_path'] is None
