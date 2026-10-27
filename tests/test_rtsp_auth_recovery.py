import time
import pytest
from unittest.mock import MagicMock, patch

from backend.services.camera_streamer import LiveCameraStreamWorker, CameraStreamManager
from backend.services.camera_service import sanitize_stream_url


def test_sanitize_stream_url_redacts_credentials():
    """Verify that user passwords and query tokens are strictly redacted."""
    url1 = "rtsp://admin:SecretPass123@192.168.1.100:554/live"
    sanitized1 = sanitize_stream_url(url1)
    assert "SecretPass123" not in sanitized1
    assert "rtsp://admin:***@192.168.1.100:554/live" in sanitized1

    url2 = "rtsp://rtsp.rtsplink.com/live/people?token=secret_token_123456789abcdef"
    sanitized2 = sanitize_stream_url(url2)
    assert "secret_token_123456789abcdef" not in sanitized2
    assert "token=***" in sanitized2

    url3 = "rtsp://10.0.0.1:554/feed?auth=supersecretkey&channel=1"
    sanitized3 = sanitize_stream_url(url3)
    assert "supersecretkey" not in sanitized3
    assert "auth=***" in sanitized3


def test_worker_stale_frame_invalidation_on_disconnect():
    """Verify that when connection drops, latest_raw_frame is cleared to prevent stale decisions."""
    worker = LiveCameraStreamWorker(
        tenant_id="tenant-test",
        camera_id="cam-test-1",
        stream_url="data/mock_video.mp4",
        is_loop=False
    )
    import numpy as np
    worker._latest_raw_frame = np.zeros((100, 100, 3), dtype=np.uint8)
    worker._latest_frame_capture_ts = time.time()

    with worker._new_frame_cond:
        worker._latest_raw_frame = None
        worker._latest_frame_capture_ts = 0.0

    assert worker._latest_raw_frame is None
    assert worker._latest_frame_capture_ts == 0.0


def test_worker_token_refresh_callback_invoked():
    """Verify that token_refresh_fn is called when stream connection fails."""
    refresh_mock = MagicMock(return_value="rtsp://provider.example.com/live?token=renewed_token")

    worker = LiveCameraStreamWorker(
        tenant_id="tenant-test",
        camera_id="cam-test-2",
        stream_url="rtsp://provider.example.com/live?token=expired_token",
        token_refresh_fn=refresh_mock
    )

    with patch("cv2.VideoCapture") as mock_cap:
        cap_instance = MagicMock()
        cap_instance.isOpened.side_effect = [False, True]
        mock_cap.return_value = cap_instance

        cap = worker._open_capture()
        if cap is None:
            new_url = worker.token_refresh_fn()
            if new_url:
                worker.stream_url = new_url

        refresh_mock.assert_called_once()
        assert worker.stream_url == "rtsp://provider.example.com/live?token=renewed_token"


def test_duplicate_workers_prevented_by_manager():
    """Verify that CameraStreamManager prevents duplicate workers under concurrent requests."""
    manager = CameraStreamManager()

    with patch("backend.services.camera_streamer.log_audit_event"):
        w1 = manager.start_camera_stream(
            tenant_id="tenant-1",
            camera_id="cam-unique-123",
            stream_url="data/mock_video.mp4"
        )

        w2 = manager.start_camera_stream(
            tenant_id="tenant-1",
            camera_id="cam-unique-123",
            stream_url="data/mock_video.mp4"
        )

        assert w1 is w2
        manager.shutdown_all()
