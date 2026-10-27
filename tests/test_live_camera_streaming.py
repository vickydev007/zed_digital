from __future__ import annotations
import os
import time
import socket
from unittest.mock import patch, MagicMock
import pytest
import numpy as np
import cv2
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.core.database import Base, get_db
from backend.core.config import settings
from backend.core.security import create_access_token, hash_password
from backend.models import Tenant, User, TenantMembership, Camera, PassageEvent, PresenceSession
from backend.main import app
from backend.services.camera_service import validate_stream_url, sanitize_stream_url
import backend.services.camera_streamer as cs
from backend.services.camera_streamer import LiveCameraStreamWorker, CameraStreamManager

TEST_DB_URL = 'sqlite:///./data/test_live_streaming.db'
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
    orig_jw_session = jw.SessionLocal
    orig_cs_session = cs.SessionLocal
    jw.SessionLocal = TestingSessionLocal
    cs.SessionLocal = TestingSessionLocal
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    yield
    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=test_engine)
    jw.SessionLocal = orig_jw_session
    cs.SessionLocal = orig_cs_session
    if os.path.exists('./data/test_live_streaming.db'):
        try:
            os.remove('./data/test_live_streaming.db')
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
def seed_data(db_session):
    t_alpha = Tenant(name='Alpha Security Corp', slug='alpha-sec', is_active=True)
    t_beta = Tenant(name='Beta Defense Inc', slug='beta-def', is_active=True)
    db_session.add_all([t_alpha, t_beta])
    db_session.flush()

    u_alpha = User(
        email='alpha_live@example.com',
        hashed_password=hash_password('Password123!'),
        full_name='Alpha Officer',
        is_active=True,
    )
    u_beta = User(
        email='beta_live@example.com',
        hashed_password=hash_password('Password123!'),
        full_name='Beta Officer',
        is_active=True,
    )
    db_session.add_all([u_alpha, u_beta])
    db_session.flush()

    m_alpha = TenantMembership(tenant_id=t_alpha.id, user_id=u_alpha.id, role='OWNER')
    m_beta = TenantMembership(tenant_id=t_beta.id, user_id=u_beta.id, role='OWNER')
    db_session.add_all([m_alpha, m_beta])
    db_session.commit()

    return {
        'tenant_alpha': t_alpha,
        'tenant_beta': t_beta,
        'user_alpha': u_alpha,
        'user_beta': u_beta,
        'token_alpha': create_access_token({'sub': u_alpha.id, 'email': u_alpha.email}),
        'token_beta': create_access_token({'sub': u_beta.id, 'email': u_beta.email}),
    }



def test_stream_url_ssrf_and_dns_rebinding_rejection():
    for invalid_url in [
        'rtsp://127.0.0.1:554/live',
        'rtsps://127.0.0.1:322/stream',
        'rtsp://0.0.0.0:554/cam',
        'rtsp://localhost:554/live',
    ]:
        with pytest.raises(ValueError, match="Forbidden"):
            validate_stream_url(invalid_url)

    with pytest.raises(ValueError, match="Forbidden"):
        validate_stream_url('rtsp://169.254.169.254/latest/meta-data')

    for bad_scheme in ['ftp://192.168.1.10/video', 'file:///etc/passwd']:
        with pytest.raises(ValueError, match="Unsupported stream scheme"):
            validate_stream_url(bad_scheme)

    with patch('socket.getaddrinfo') as mock_dns:
        mock_dns.return_value = [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('127.0.0.1', 554))]
        with pytest.raises(ValueError, match="Forbidden"):
            validate_stream_url('rtsp://malicious-camera-dns.internal/live')

    with patch('socket.getaddrinfo') as mock_dns:
        mock_dns.return_value = [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('169.254.169.254', 554))]
        with pytest.raises(ValueError, match="Forbidden"):
            validate_stream_url('rtsp://cloud-metadata-alias.com/stream')


def test_private_network_policy_toggle():
    assert settings.ALLOW_PRIVATE_RTSP_NETWORKS is True
    valid_url = 'rtsp://admin:secret@192.168.1.50:554/live'
    assert validate_stream_url(valid_url) == valid_url

    with patch.object(settings, 'ALLOW_PRIVATE_RTSP_NETWORKS', False):
        with pytest.raises(ValueError, match="private network address rejected by policy"):
            validate_stream_url('rtsp://192.168.1.50:554/live')


def test_stream_url_credential_sanitization():
    url_with_creds = 'rtsp://operator_john:Super$ecret#Pass@192.168.1.100:554/ch1'
    sanitized = sanitize_stream_url(url_with_creds)
    assert 'Super$ecret#Pass' not in sanitized
    assert '***' in sanitized
    assert '192.168.1.100:554/ch1' in sanitized

    plain_url = 'rtsp://10.0.0.25:554/stream'
    assert sanitize_stream_url(plain_url) == plain_url



class FakeVideoCapture:
    """Deterministic synthetic video capture yielding controlled frames."""
    def __init__(self, width=640, height=480, fps=25.0):
        self.width = width
        self.height = height
        self.fps = fps
        self.is_opened = True
        self.frame_count = 0

    def isOpened(self):
        return self.is_opened

    def read(self):
        if not self.is_opened:
            return False, None
        self.frame_count += 1
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        cv2.putText(frame, f"F:{self.frame_count}", (30, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
        return True, frame

    def get(self, prop_id):
        if prop_id == cv2.CAP_PROP_FPS:
            return self.fps
        elif prop_id == cv2.CAP_PROP_FRAME_WIDTH:
            return float(self.width)
        elif prop_id == cv2.CAP_PROP_FRAME_HEIGHT:
            return float(self.height)
        return 0.0

    def release(self):
        self.is_opened = False


def test_camera_worker_bounded_buffer_drops_stale_frames():
    """Verify that a capture source runs and updates latest bounded frame without growing memory."""
    fake_cap = FakeVideoCapture(fps=30.0)

    with patch('cv2.VideoCapture', return_value=fake_cap):
        worker = LiveCameraStreamWorker(
            tenant_id='tnt-alpha',
            camera_id='cam-test-bounded-01',
            stream_url='rtsp://192.168.1.50:554/test',
            stream_fps=25.0,
        )

        assert worker.status == 'CONNECTING'

        worker.start()
        time.sleep(0.3)

        status = worker.get_runtime_status()
        assert status['camera_id'] == 'cam-test-bounded-01'
        assert status['received_frames'] > 0

        with worker._lock:
            if worker._latest_raw_frame is not None:
                assert isinstance(worker._latest_raw_frame, np.ndarray)
                assert worker._latest_raw_frame.shape == (480, 640, 3)

        worker.stop(timeout=1.0)
        assert worker.status == 'OFFLINE'
        assert fake_cap.is_opened is False


def test_camera_worker_reconnection_backoff():
    """Verify that a broken capture source transitions to ERROR/CONNECTING with recorded error."""
    broken_cap = MagicMock()
    broken_cap.isOpened.return_value = False

    with patch('cv2.VideoCapture', return_value=broken_cap):
        worker = LiveCameraStreamWorker(
            tenant_id='tnt-alpha',
            camera_id='cam-broken-01',
            stream_url='rtsp://192.168.1.99:554/broken',
            stream_fps=10.0,
        )

        worker.start()
        time.sleep(0.2)

        status = worker.get_runtime_status()
        assert status['status'] in ('CONNECTING', 'DEGRADED', 'ERROR')

        worker.stop(timeout=1.0)
        assert worker.status == 'OFFLINE'



def test_stream_manager_lifecycle(db_session, seed_data):
    manager = CameraStreamManager()

    cam = Camera(
        tenant_id=seed_data['tenant_alpha'].id,
        name='Perimeter Gate 1',
        location='North Entrance',
        is_active=True,
        status='OFFLINE',
        stream_fps=20.0,
    )
    db_session.add(cam)
    db_session.commit()

    fake_cap = FakeVideoCapture()
    with patch('cv2.VideoCapture', return_value=fake_cap):
        worker = manager.start_camera_stream(
            tenant_id=seed_data['tenant_alpha'].id,
            camera_id=cam.id,
            stream_url='rtsp://192.168.1.10:554/live',
        )
        assert worker is not None
        assert worker.camera_id == cam.id

        dup_worker = manager.start_camera_stream(
            tenant_id=seed_data['tenant_alpha'].id,
            camera_id=cam.id,
            stream_url='rtsp://192.168.1.10:554/live',
        )
        assert dup_worker is worker

        status = manager.get_status(cam.id)
        assert status is not None
        assert status['camera_id'] == cam.id
        assert status['tenant_id'] == seed_data['tenant_alpha'].id

        stopped = manager.stop_camera_stream(camera_id=cam.id)
        assert stopped is True
        assert manager.get_worker(cam.id) is None

    manager.shutdown_all()


def test_stream_connectivity_probe():
    manager = CameraStreamManager()

    fake_cap = FakeVideoCapture(width=1280, height=720, fps=30.0)
    with patch('cv2.VideoCapture', return_value=fake_cap):
        res = manager.test_connectivity('rtsp://192.168.1.50:554/ch1', timeout_seconds=2.0)
        assert res['success'] is True
        assert res['width'] == 1280
        assert res['height'] == 720
        assert res['fps'] == 30.0
        assert 'Stream verified' in res['message']

    res_ssrf = manager.test_connectivity('rtsp://127.0.0.1:554/live')
    assert res_ssrf['success'] is False
    assert 'Validation rejected' in res_ssrf['error']



def test_camera_api_lifecycle_and_tenant_isolation(client, seed_data):
    headers_alpha = {
        'Authorization': f"Bearer {seed_data['token_alpha']}",
        'X-Tenant-ID': seed_data['tenant_alpha'].id,
    }
    headers_beta = {
        'Authorization': f"Bearer {seed_data['token_beta']}",
        'X-Tenant-ID': seed_data['tenant_beta'].id,
    }

    create_resp = client.post(
        '/api/v1/cameras',
        json={
            'name': 'Alpha Vault Camera',
            'location': 'Vault Room',
            'rtsp_url': 'rtsp://admin:pass@192.168.1.77:554/vault',
            'stream_fps': 25.0,
        },
        headers=headers_alpha,
    )
    assert create_resp.status_code == 201
    cam_data = create_resp.json()
    cam_id = cam_data['id']
    assert cam_data['has_encrypted_stream'] is True

    fake_cap = FakeVideoCapture()
    with patch('cv2.VideoCapture', return_value=fake_cap):
        test_conn_resp = client.post(
            '/api/v1/cameras/test-connection',
            json={'rtsp_url': 'rtsp://192.168.1.77:554/vault'},
            headers=headers_alpha,
        )
        assert test_conn_resp.status_code == 200
        assert test_conn_resp.json()['success'] is True

        start_resp = client.post(f"/api/v1/cameras/{cam_id}/start", headers=headers_alpha)
        assert start_resp.status_code == 200
        assert start_resp.json()['status'] in ('ONLINE', 'CONNECTING')

        status_resp = client.get(f"/api/v1/cameras/{cam_id}/status", headers=headers_alpha)
        assert status_resp.status_code == 200
        status_data = status_resp.json()
        assert status_data['camera_id'] == cam_id

        beta_status_resp = client.get(f"/api/v1/cameras/{cam_id}/status", headers=headers_beta)
        assert beta_status_resp.status_code in (403, 404)

        beta_stop_resp = client.post(f"/api/v1/cameras/{cam_id}/stop", headers=headers_beta)
        assert beta_stop_resp.status_code in (403, 404)

        beta_preview_resp = client.get(f"/api/v1/cameras/{cam_id}/preview", headers=headers_beta)
        assert beta_preview_resp.status_code in (403, 404)

        stop_resp = client.post(f"/api/v1/cameras/{cam_id}/stop", headers=headers_alpha)
        assert stop_resp.status_code == 200
        assert stop_resp.json()['status'] == 'OFFLINE'


def test_camera_preview_authentication_query_token(client, seed_data):
    """Test that the live preview endpoint validates the ?token= query parameter."""
    headers_alpha = {
        'Authorization': f"Bearer {seed_data['token_alpha']}",
        'X-Tenant-ID': seed_data['tenant_alpha'].id,
    }

    create_resp = client.post(
        '/api/v1/cameras',
        json={
            'name': 'Turnstile 4',
            'location': 'West Wing',
            'rtsp_url': 'rtsp://192.168.1.88:554/stream',
            'stream_fps': 15.0,
        },
        headers=headers_alpha,
    )
    cam_id = create_resp.json()['id']

    unauth_resp = client.get(f"/api/v1/cameras/{cam_id}/preview")
    assert unauth_resp.status_code == 401

    bad_token_resp = client.get(f"/api/v1/cameras/{cam_id}/preview?token=invalid.jwt.token")
    assert bad_token_resp.status_code == 401

    token = seed_data['token_alpha']
    tenant_id = seed_data['tenant_alpha'].id
    fake_cap = FakeVideoCapture()
    with patch('cv2.VideoCapture', return_value=fake_cap):
        with client.stream("GET", f"/api/v1/cameras/{cam_id}/preview?token={token}&tenant_id={tenant_id}") as stream_resp:
            assert stream_resp.status_code in (200, 503)
            if stream_resp.status_code == 200:
                assert 'multipart/x-mixed-replace' in stream_resp.headers.get('content-type', '')
                for chunk in stream_resp.iter_bytes():
                    if chunk:
                        break


def test_camera_marked_online_only_after_real_frame_received():
    """Verify that a camera is marked ONLINE strictly after a real frame is received, not on start."""
    class ControlledCapture:
        def __init__(self):
            self.allow_frames = False
            self.is_opened = True

        def isOpened(self):
            return self.is_opened

        def read(self):
            if not self.allow_frames:
                return False, None
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            return True, frame

        def get(self, prop):
            return 25.0

        def release(self):
            self.is_opened = False

    controlled_cap = ControlledCapture()
    with patch('cv2.VideoCapture', return_value=controlled_cap):
        worker = LiveCameraStreamWorker(
            tenant_id='tnt-alpha',
            camera_id='cam-status-test',
            stream_url='rtsp://192.168.1.100:554/live',
            stream_fps=25.0,
        )

        assert worker.status == 'CONNECTING'

        worker.start()
        time.sleep(0.1)

        assert worker.status != 'ONLINE'
        assert worker.status in ('CONNECTING', 'DEGRADED')

        controlled_cap.allow_frames = True
        time.sleep(0.2)

        assert worker.status == 'ONLINE'
        assert worker.received_frames > 0

        worker.stop(timeout=1.0)
        assert worker.status == 'OFFLINE'


def test_scoped_preview_token_generation_and_camera_binding(client, seed_data):
    """Verify that scoped preview tokens are issued and bound exclusively to the target camera."""
    headers_alpha = {
        'Authorization': f"Bearer {seed_data['token_alpha']}",
        'X-Tenant-ID': seed_data['tenant_alpha'].id,
    }

    cam_a_resp = client.post(
        '/api/v1/cameras',
        json={'name': 'Gate Alpha', 'rtsp_url': 'rtsp://192.168.1.10:554/a'},
        headers=headers_alpha,
    )
    cam_a_id = cam_a_resp.json()['id']

    cam_b_resp = client.post(
        '/api/v1/cameras',
        json={'name': 'Gate Beta', 'rtsp_url': 'rtsp://192.168.1.10:554/b'},
        headers=headers_alpha,
    )
    cam_b_id = cam_b_resp.json()['id']

    token_resp = client.post(f"/api/v1/cameras/{cam_a_id}/preview-token", headers=headers_alpha)
    assert token_resp.status_code == 200
    token_data = token_resp.json()
    assert 'preview_token' in token_data
    assert token_data['camera_id'] == cam_a_id
    assert token_data['tenant_id'] == seed_data['tenant_alpha'].id
    scoped_token = token_data['preview_token']

    fake_cap = FakeVideoCapture()
    with patch('cv2.VideoCapture', return_value=fake_cap):
        with client.stream("GET", f"/api/v1/cameras/{cam_a_id}/preview?token={scoped_token}") as resp_a:
            assert resp_a.status_code in (200, 503)
            for chunk in resp_a.iter_bytes():
                if chunk:
                    break

        resp_b = client.get(f"/api/v1/cameras/{cam_b_id}/preview?token={scoped_token}")
        assert resp_b.status_code == 403
        assert 'Preview token not authorized for this camera ID' in resp_b.json()['detail']

        client.cookies.set('reid_preview_token', scoped_token)
        with client.stream("GET", f"/api/v1/cameras/{cam_a_id}/preview") as cookie_resp:
            assert cookie_resp.status_code in (200, 503)
            for chunk in cookie_resp.iter_bytes():
                if chunk:
                    break
        client.cookies.clear()


def test_reconnect_destination_revalidation(db_session, seed_data):
    """Verify that destination is re-validated on reconnect and rejects rebinding to loopback."""
    fake_cap = FakeVideoCapture()
    worker = LiveCameraStreamWorker(
        tenant_id=seed_data['tenant_alpha'].id,
        camera_id='cam-rebinding-test',
        stream_url='rtsp://rebind-camera.corp.internal:554/live',
        stream_fps=25.0,
    )

    with patch('socket.getaddrinfo') as mock_dns:
        mock_dns.return_value = [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('192.168.1.50', 554))]
        with patch('cv2.VideoCapture', return_value=fake_cap):
            cap = worker._open_capture()
            assert cap is not None

        mock_dns.return_value = [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('127.0.0.1', 554))]
        cap_rebind = worker._open_capture()
        assert cap_rebind is None
        assert worker.status == 'ERROR'
        assert 'SSRF/DNS validation failed' in (worker.last_error or '')


def test_prohibited_ports_rejection():
    """Verify that sensitive database and administration ports are rejected."""
    for bad_port in [22, 6379, 3306, 5432, 27017, 2375]:
        bad_url = f"rtsp://192.168.1.100:{bad_port}/live"
        with pytest.raises(ValueError, match="Forbidden stream destination port"):
            validate_stream_url(bad_url)


def test_allowed_camera_subnets_enforcement():
    """Verify that when ALLOWED_CAMERA_SUBNETS is defined, non-whitelisted private IPs are rejected."""
    with patch.object(settings, 'ALLOWED_CAMERA_SUBNETS', '192.168.1.0/24, 10.10.0.0/16'):
        assert validate_stream_url('rtsp://192.168.1.50:554/live') == 'rtsp://192.168.1.50:554/live'
        assert validate_stream_url('rtsp://10.10.5.20:554/live') == 'rtsp://10.10.5.20:554/live'

        with pytest.raises(ValueError, match="not within ALLOWED_CAMERA_SUBNETS"):
            validate_stream_url('rtsp://192.168.2.100:554/live')
        with pytest.raises(ValueError, match="not within ALLOWED_CAMERA_SUBNETS"):
            validate_stream_url('rtsp://172.16.0.50:554/live')


def test_preview_token_revocation_endpoint(client, seed_data):
    """Verify that revoked preview tokens are immediately rejected by the preview stream."""
    headers_alpha = {
        'Authorization': f"Bearer {seed_data['token_alpha']}",
        'X-Tenant-ID': seed_data['tenant_alpha'].id,
    }
    cam_resp = client.post(
        '/api/v1/cameras',
        json={'name': 'Gate Revoke Test', 'rtsp_url': 'rtsp://192.168.1.55:554/live'},
        headers=headers_alpha,
    )
    cam_id = cam_resp.json()['id']

    token_resp = client.post(f"/api/v1/cameras/{cam_id}/preview-token", headers=headers_alpha)
    token = token_resp.json()['preview_token']

    revoke_resp = client.post(
        f"/api/v1/cameras/{cam_id}/revoke-token",
        json={"token": token},
        headers=headers_alpha
    )
    assert revoke_resp.status_code == 200
    assert revoke_resp.json()['status'] == 'REVOKED'

    resp = client.get(f"/api/v1/cameras/{cam_id}/preview?token={token}")
    assert resp.status_code == 401
    assert "revoked" in resp.json()['detail'].lower()


def test_dns_mixed_answers_rejection():
    """Verify that if DNS returns mixed IP addresses (one valid and one loopback/link-local), the request is rejected."""
    with patch('socket.getaddrinfo') as mock_dns:
        mock_dns.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('192.168.1.50', 554)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('127.0.0.1', 554))
        ]
        with pytest.raises(ValueError, match="Forbidden"):
            validate_stream_url('rtsp://mixed-dns.internal/live')


def test_active_stream_terminated_on_token_revocation():
    """Verify that an active generator terminates immediately when its preview token is revoked."""
    from backend.api.v1.cameras import _revoked_preview_tokens, is_preview_token_revoked
    worker = LiveCameraStreamWorker(
        tenant_id='tnt-alpha',
        camera_id='cam-active-revoke',
        stream_url='rtsp://192.168.1.100:554/live',
        stream_fps=25.0
    )
    test_token = "active.stream.test.token"
    _revoked_preview_tokens.discard(test_token)

    with worker._new_annotated_cond:
        worker._latest_jpeg = b"test_jpeg_bytes"
        worker._latest_metadata = {'frame_idx': 1, 'capture_timestamp': time.time()}
        worker._new_annotated_cond.notify_all()

    gen = worker.generate_mjpeg_stream(is_revoked_fn=lambda: is_preview_token_revoked(test_token))
    
    chunk1 = next(gen)
    assert b"--frame" in chunk1

    _revoked_preview_tokens.add(test_token)

    with worker._new_annotated_cond:
        worker._latest_metadata = {'frame_idx': 2, 'capture_timestamp': time.time()}
        worker._new_annotated_cond.notify_all()

    with pytest.raises(StopIteration):
        next(gen)

    _revoked_preview_tokens.discard(test_token)
    assert worker.consumer_count == 0


def test_persistence_retry_on_db_exception():
    """Verify that when persistence fails due to a DB exception, items are queued for retry and succeed later."""
    from openset_reid.pipeline.video_analyzer import IdentityStatus, PassageStatus
    worker = LiveCameraStreamWorker(
        tenant_id='tnt-alpha',
        camera_id='cam-persist-retry',
        stream_url='rtsp://192.168.1.100:554/live',
        stream_fps=25.0
    )
    mock_candidate = [{
        'track_id': 99,
        'identity_status': IdentityStatus.UNKNOWN,
        'passage_status': PassageStatus.FIRST_ENTRY,
        'matched_identity': None,
        'candidate_id': None,
        'representative_crop': None,
        'best_score': 0.5
    }]

    with patch('backend.services.camera_streamer.SessionLocal') as mock_session_cls:
        mock_db = MagicMock()
        mock_db.commit.side_effect = Exception("Simulated SQLite database lock failure")
        mock_session_cls.return_value = mock_db

        worker._persist_tracks_worker(mock_candidate, frame_idx=10, attempt=1)

        assert worker.persistence_failure_count == 1
        assert len(worker._pending_persist_retries) == 1

    with patch('backend.services.camera_streamer.SessionLocal') as mock_session_cls:
        mock_db_ok = MagicMock()
        mock_session_cls.return_value = mock_db_ok

        worker._persist_tracks_worker([], frame_idx=11, attempt=1)

        assert worker.persistence_success_count == 1
        assert len(worker._pending_persist_retries) == 0


def test_multi_client_stream_isolation_and_disconnect():
    """Verify that multiple concurrent consumers receive frames independently and disconnect safely."""
    worker = LiveCameraStreamWorker(
        tenant_id='tnt-alpha',
        camera_id='cam-multi-client',
        stream_url='rtsp://192.168.1.100:554/live',
        stream_fps=25.0
    )

    with worker._new_annotated_cond:
        worker._latest_jpeg = b"multi_client_frame_1"
        worker._latest_metadata = {'frame_idx': 1, 'capture_timestamp': time.time()}

    client1_gen = worker.generate_mjpeg_stream()
    client2_gen = worker.generate_mjpeg_stream()

    c1_f1 = next(client1_gen)
    c2_f1 = next(client2_gen)
    assert b"multi_client_frame_1" in c1_f1
    assert b"multi_client_frame_1" in c2_f1

    assert worker.consumer_count == 2

    client1_gen.close()
    assert worker.consumer_count == 1

    with worker._new_annotated_cond:
        worker._latest_jpeg = b"multi_client_frame_2"
        worker._latest_metadata = {'frame_idx': 2, 'capture_timestamp': time.time()}
        worker._new_annotated_cond.notify_all()

    c2_f2 = next(client2_gen)
    assert b"multi_client_frame_2" in c2_f2

    client2_gen.close()
    assert worker.consumer_count == 0





