from __future__ import annotations
import os
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Dict, Any, Generator, Tuple, List, Callable
from collections import deque
from datetime import datetime, timezone
import cv2
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.core.database import SessionLocal
from backend.core.config import settings
from backend.core.security import decrypt_secret
from backend.models.camera import Camera
from backend.models.worker import Worker, PersonEmbedding
from backend.models.candidate import CandidateIdentity
from backend.models.passage import PassageEvent, PresenceSession
from backend.models.crop import RepresentativeCrop
from backend.services.camera_service import validate_stream_url, sanitize_stream_url, get_camera_by_id
from backend.services.audit_service import log_audit_event
from openset_reid.pipeline.video_analyzer import (
    OfflineVideoAnalyzer,
    IdentityStatus,
    PassageStatus,
    PersonCategory,
    resolve_display_category
)

class LiveCameraStreamWorker:

    def __init__(self, tenant_id: str, camera_id: str, stream_url: str, stream_fps: float = 25.0, is_loop: bool = False, db: Optional[Session] = None, token_refresh_fn: Optional[Callable[[], Optional[str]]] = None):
        self.tenant_id = tenant_id
        self.camera_id = camera_id
        self.stream_url = stream_url
        self.target_fps = stream_fps or 25.0
        self.is_loop = is_loop
        self.token_refresh_fn = token_refresh_fn

        self.status = 'CONNECTING'
        self.last_error: Optional[str] = None
        self.reconnect_count = 0
        self.start_time = time.time()
        self.last_frame_time: Optional[float] = None
        self.received_frames = 0
        self.processed_frames = 0
        self.received_fps = 0.0
        self.processed_fps = 0.0

        self.active_tracks_count = 0
        self.consumer_count = 0

        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._new_frame_cond = threading.Condition(self._lock)
        self._new_annotated_cond = threading.Condition(self._lock)

        self._latest_raw_frame: Optional[np.ndarray] = None
        self._latest_frame_capture_ts: float = 0.0
        self._latency_samples: deque = deque(maxlen=2000)
        self._client_latency_samples: deque = deque(maxlen=2000)
        self._latest_jpeg: Optional[bytes] = None
        self._latest_metadata: Dict[str, Any] = {}
        self._persist_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix=f"cam-db-{camera_id[:6]}")
        self.persistence_success_count: int = 0
        self.persistence_failure_count: int = 0
        self._pending_persist_retries: List[Tuple[List[Dict[str, Any]], int, int]] = []
        self._persist_retry_lock = threading.Lock()

        inference_device = getattr(settings, 'CAMERA_INFERENCE_DEVICE', 'auto')
        self.analyzer = OfflineVideoAnalyzer(
            onnx_model_path=settings.ONNX_MODEL_PATH,
            score_threshold=settings.DEFAULT_SCORE_THRESHOLD,
            contrast_margin=settings.DEFAULT_CONTRAST_MARGIN,
            min_observations=settings.DEFAULT_MIN_OBSERVATIONS,
            policy_id=settings.ACTIVE_POLICY_ID,
            quality_min_h=settings.DEFAULT_QUALITY_MIN_H,
            quality_min_w=settings.DEFAULT_QUALITY_MIN_W,
            quality_min_blur=settings.DEFAULT_QUALITY_MIN_BLUR,
            device=inference_device,
            camera_id=self.camera_id
        )
        self.camera_profile = self.analyzer.camera_profile
        self.is_c5_profile = (self.camera_profile.profile_id == 'PROFILE-C5-PHOTOMETRIC-V1')
        self._init_enrolled_workers(db=db)

        self._capture_thread = threading.Thread(target=self._capture_loop, name=f"cam-cap-{camera_id[:8]}", daemon=True)
        self._inference_thread = threading.Thread(target=self._inference_loop, name=f"cam-inf-{camera_id[:8]}", daemon=True)

    def _init_enrolled_workers(self, db: Optional[Session] = None):
        close_db = False
        session_to_use = db
        if session_to_use is None:
            session_to_use = SessionLocal()
            close_db = True
        try:
            stmt = (
                select(PersonEmbedding, Worker)
                .join(Worker, PersonEmbedding.worker_id == Worker.id)
                .where(
                    PersonEmbedding.tenant_id == self.tenant_id,
                    Worker.is_active == True,
                    Worker.enrollment_status == 'ENROLLED'
                )
            )
            records = session_to_use.execute(stmt).all()
            for p_emb, worker in records:
                vec = np.array(p_emb.embedding_vector, dtype=np.float32)
                self.analyzer.matcher.enroll(worker.staff_code, vec)
        except Exception:
            pass
        finally:
            if close_db:
                session_to_use.close()


    def start(self):
        self._capture_thread.start()
        self._inference_thread.start()

    def stop(self, timeout: float = 3.0):
        self._stop_event.set()
        with self._new_frame_cond:
            self._new_frame_cond.notify_all()
        with self._new_annotated_cond:
            self._new_annotated_cond.notify_all()
        
        self._capture_thread.join(timeout=timeout)
        self._inference_thread.join(timeout=timeout)
        try:
            self._persist_executor.shutdown(wait=True)
        except Exception:
            pass
        self.status = 'OFFLINE'
        self._update_db_status('OFFLINE')

    def _update_db_status(self, new_status: str):
        db: Session = SessionLocal()
        try:
            cam = db.execute(select(Camera).where(Camera.tenant_id == self.tenant_id, Camera.id == self.camera_id)).scalar_one_or_none()
            if cam:
                cam.status = new_status
                if new_status == 'ONLINE':
                    cam.last_heartbeat = datetime.now(timezone.utc)
                db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()
    def _open_capture(self) -> Optional[cv2.VideoCapture]:
        if not os.path.isfile(self.stream_url):
            try:
                validate_stream_url(self.stream_url)
            except Exception as exc:
                sanitized = sanitize_stream_url(self.stream_url)
                self.last_error = f"SSRF/DNS validation failed for '{sanitized}': {str(exc)}"
                self.status = 'ERROR'
                return None

        if os.path.isfile(self.stream_url):
            cap = cv2.VideoCapture(self.stream_url)
        else:
            os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"
            timeout_ms = int(getattr(settings, 'CAMERA_CONNECT_TIMEOUT_SECONDS', 5.0) * 1000)
            cap = cv2.VideoCapture(
                self.stream_url,
                cv2.CAP_FFMPEG,
                [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, timeout_ms, cv2.CAP_PROP_READ_TIMEOUT_MSEC, timeout_ms]
            )

        if not cap.isOpened():
            cap.release()
            return None
        return cap

    def _capture_loop(self):
        backoff = 1.0
        fps_timer = time.time()
        fps_count = 0

        while not self._stop_event.is_set():
            cap = self._open_capture()
            if cap is None or not cap.isOpened():
                if self.token_refresh_fn is not None:
                    try:
                        new_url = self.token_refresh_fn()
                        if new_url and new_url != self.stream_url:
                            self.stream_url = new_url
                            cap = self._open_capture()
                    except Exception:
                        pass

                if cap is None or not cap.isOpened():
                    is_tokenized = "token=" in self.stream_url.lower() or "auth=" in self.stream_url.lower()
                    if is_tokenized and self.reconnect_count >= 3:
                        self.status = 'AUTH_EXPIRED'
                        self.last_error = "RTSP token expired / authentication rejected (401). Awaiting token refresh."
                    else:
                        self.status = 'CONNECTING' if self.reconnect_count == 0 else 'DEGRADED'
                        self.last_error = f"Connection failed. Retry in {backoff:.1f}s"
                    self.reconnect_count += 1
                    import random
                    jitter = random.uniform(0.1, 0.4)
                    time.sleep(backoff + jitter)
                    backoff = min(settings.CAMERA_RECONNECT_MAX_BACKOFF, backoff * 1.5)
                    continue

            backoff = 1.0
            self.last_error = None

            is_file_source = os.path.isfile(self.stream_url)
            frame_delay = 1.0 / max(1.0, self.target_fps)
            last_frame_perf = time.perf_counter()

            consecutive_read_failures = 0
            while not self._stop_event.is_set():
                if is_file_source:
                    time_diff = time.perf_counter() - last_frame_perf
                    if time_diff < frame_delay:
                        time.sleep(frame_delay - time_diff)
                    last_frame_perf = time.perf_counter()

                ret, frame = cap.read()
                if not ret or frame is None:
                    consecutive_read_failures += 1
                    if consecutive_read_failures >= 10:
                        if (self.is_loop or os.path.isfile(self.stream_url)) and os.path.exists(self.stream_url):
                            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                            consecutive_read_failures = 0
                            continue
                        break
                    time.sleep(0.04)
                    continue

                consecutive_read_failures = 0


                if self.status != 'ONLINE':
                    self.status = 'ONLINE'
                    self._update_db_status('ONLINE')

                now = time.time()
                self.last_frame_time = now
                self.received_frames += 1
                fps_count += 1
                if now - fps_timer >= 1.0:
                    self.received_fps = round(fps_count / (now - fps_timer), 1)
                    fps_count = 0
                    fps_timer = now


                with self._new_frame_cond:
                    self._latest_raw_frame = frame
                    self._latest_frame_capture_ts = now
                    self._new_frame_cond.notify()

            cap.release()
            with self._new_frame_cond:
                self._latest_raw_frame = None
                self._latest_frame_capture_ts = 0.0
            if not self._stop_event.is_set():
                self.status = 'DEGRADED'
                self.reconnect_count += 1
                self.last_error = 'Stream connection lost. Reconnecting...'
                time.sleep(1.0)

    def _inference_loop(self):
        fps_timer = time.time()
        fps_count = 0
        frame_idx = 0
        boxes = []

        while not self._stop_event.is_set():
            frame = None
            cap_ts = 0.0
            with self._new_frame_cond:
                while self._latest_raw_frame is None and not self._stop_event.is_set():
                    self._new_frame_cond.wait(timeout=0.2)
                if self._stop_event.is_set():
                    break
                frame = self._latest_raw_frame
                cap_ts = self._latest_frame_capture_ts or time.time()
                self._latest_raw_frame = None

            if frame is None:
                continue

            dequeue_time = time.time()
            frame_age_ms = max(0.0, (dequeue_time - (cap_ts or dequeue_time)) * 1000.0)

            frame_idx += 1

            t_inf_start = time.perf_counter()
            sample_rate = max(1, settings.CAMERA_INFERENCE_SAMPLE_RATE)
            if frame_idx % sample_rate == 0 or len(self.analyzer.active_tracks) == 0:
                try:
                    boxes = self.analyzer.detect_people(frame)
                except Exception:
                    boxes = []
            
            try:
                self.analyzer.update_tracks(frame, boxes, frame_idx)
                if len(self.analyzer.finished_tracks) > 100:
                    self.analyzer.finished_tracks = self.analyzer.finished_tracks[-50:]
                if len(self.analyzer.session_registry) > 300:
                    oldest_keys = list(self.analyzer.session_registry.keys())[:-200]
                    for k in oldest_keys:
                        self.analyzer.session_registry.pop(k, None)
            except Exception:
                pass
            t_inf_end = time.perf_counter()
            inf_duration_ms = (t_inf_end - t_inf_start) * 1000.0
            inference_done_ts = time.time()

            t_pers_start = time.perf_counter()
            confirmed_candidates = []
            for trk in self.analyzer.active_tracks:
                seen = trk.get('seen_frames', 1)
                logged = trk.get('live_event_logged', False)
                if seen >= 4 and not logged:
                    trk['live_event_logged'] = True
                    confirmed_candidates.append(dict(trk))

            if confirmed_candidates:
                try:
                    self._persist_executor.submit(self._persist_tracks_worker, confirmed_candidates, frame_idx)
                except Exception:
                    pass
            t_pers_end = time.perf_counter()
            pers_duration_ms = (t_pers_end - t_pers_start) * 1000.0

            now = time.time()
            fps_count += 1
            if now - fps_timer >= 1.0:
                self.processed_fps = round(fps_count / (now - fps_timer), 1)
                fps_count = 0
                fps_timer = now

            t_enc_start = time.perf_counter()
            try:
                annotated = self.analyzer.render_hud_and_boxes(frame, frame_idx, self.processed_fps)
                _, jpeg_buf = cv2.imencode('.jpg', annotated, [cv2.IMWRITE_JPEG_QUALITY, 75])
                jpeg_bytes = jpeg_buf.tobytes()
            except Exception:
                jpeg_bytes = None
            t_enc_end = time.perf_counter()
            jpeg_encode_ms = (t_enc_end - t_enc_start) * 1000.0

            server_pipeline_latency_ms = frame_age_ms + inf_duration_ms + pers_duration_ms + jpeg_encode_ms

            with self._new_annotated_cond:
                self._latest_jpeg = jpeg_bytes
                self.active_tracks_count = len(self.analyzer.active_tracks)
                self.processed_frames += 1
                self._latest_metadata = {
                    'frame_idx': frame_idx,
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'capture_timestamp': cap_ts,
                    'inference_done_timestamp': inference_done_ts,
                    'frame_age_ms': round(frame_age_ms, 2),
                    'inference_duration_ms': round(inf_duration_ms, 2),
                    'persistence_duration_ms': round(pers_duration_ms, 2),
                    'jpeg_encode_ms': round(jpeg_encode_ms, 2),
                    'server_pipeline_latency_ms': round(server_pipeline_latency_ms, 2),
                    'active_tracks': self.active_tracks_count,
                    'processed_fps': self.processed_fps,
                    'received_fps': self.received_fps
                }
                self._latency_samples.append({
                    'frame_idx': frame_idx,
                    'capture_timestamp': cap_ts,
                    'frame_age_ms': frame_age_ms,
                    'inference_duration_ms': inf_duration_ms,
                    'persistence_duration_ms': pers_duration_ms,
                    'jpeg_encode_ms': jpeg_encode_ms,
                    'server_pipeline_latency_ms': server_pipeline_latency_ms
                })
                self._new_annotated_cond.notify_all()

    def _persist_tracks_worker(self, confirmed_candidates: List[Dict[str, Any]], frame_idx: int, attempt: int = 1):
        pending = []
        with self._persist_retry_lock:
            if self._pending_persist_retries:
                pending = list(self._pending_persist_retries)
                self._pending_persist_retries.clear()

        all_to_persist = list(confirmed_candidates)
        for ret_candidates, _, _ in pending:
            all_to_persist.extend(ret_candidates)

        db: Session = SessionLocal()
        try:
            for trk in all_to_persist:
                t_num = trk['track_id']
                id_status = trk['identity_status']
                pass_status = trk['passage_status']
                disp_cat = resolve_display_category(id_status, pass_status).value
                matched_code = trk.get('matched_identity')
                cand_id = trk.get('candidate_id')
                rep_crop = trk.get('representative_crop')

                worker_obj = None
                if id_status == IdentityStatus.OFFICIAL_WORKER and matched_code:
                    w_stmt = select(Worker).where(Worker.tenant_id == self.tenant_id, Worker.staff_code == matched_code)
                    worker_obj = db.execute(w_stmt).scalar_one_or_none()

                cand_obj = None
                if id_status == IdentityStatus.NEW_CANDIDATE and cand_id is not None:
                    cand_code = f"CAND_{self.camera_id[:8]}_{cand_id:03d}"
                    c_stmt = select(CandidateIdentity).where(CandidateIdentity.tenant_id == self.tenant_id, CandidateIdentity.candidate_code == cand_code)
                    cand_obj = db.execute(c_stmt).scalar_one_or_none()
                    if not cand_obj:
                        cand_obj = CandidateIdentity(
                            tenant_id=self.tenant_id,
                            candidate_code=cand_code,
                            first_seen_at=datetime.now(timezone.utc),
                            last_seen_at=datetime.now(timezone.utc),
                            review_status='PROVISIONAL',
                            notes=f"Discovered in live camera {self.camera_id} track #{t_num}"
                        )
                        db.add(cand_obj)
                        db.flush()

                crop_path = None
                if rep_crop is not None:
                    try:
                        crop_dir = os.path.join(settings.CROPS_DIR, self.tenant_id, 'live', self.camera_id)
                        os.makedirs(crop_dir, exist_ok=True)
                        crop_fname = f"live_{self.camera_id[:8]}_trk{t_num}_{disp_cat}.jpg"
                        crop_path = os.path.join(crop_dir, crop_fname)
                        cv2.imwrite(crop_path, rep_crop)
                    except Exception:
                        crop_path = None

                event = PassageEvent(
                    tenant_id=self.tenant_id,
                    camera_id=self.camera_id,
                    video_job_id=None,
                    track_id=None,
                    worker_id=worker_obj.id if worker_obj else None,
                    candidate_identity_id=cand_obj.id if cand_obj else None,
                    identity_status=id_status.value if hasattr(id_status, 'value') else str(id_status),
                    passage_status=pass_status.value if hasattr(pass_status, 'value') else str(pass_status),
                    display_category=disp_cat,
                    confidence_score=float(trk.get('best_score', 0.0)),
                    policy_id=settings.ACTIVE_POLICY_ID,
                    crop_path=crop_path,
                    event_timestamp=datetime.now(timezone.utc)
                )
                db.add(event)

                if worker_obj:
                    sess_stmt = select(PresenceSession).where(
                        PresenceSession.tenant_id == self.tenant_id,
                        PresenceSession.worker_id == worker_obj.id,
                        PresenceSession.is_currently_present == True
                    )
                    active_sess = db.execute(sess_stmt).scalar_one_or_none()
                    if active_sess:
                        active_sess.passage_count += 1
                        active_sess.last_seen_at = datetime.now(timezone.utc)
                    else:
                        new_sess = PresenceSession(
                            tenant_id=self.tenant_id,
                            worker_id=worker_obj.id,
                            identity_status=id_status.value if hasattr(id_status, 'value') else str(id_status),
                            is_currently_present=True,
                            passage_count=1
                        )
                        db.add(new_sess)

            db.commit()
            self.persistence_success_count += len(all_to_persist)
        except Exception:
            db.rollback()
            self.persistence_failure_count += len(all_to_persist)
            if attempt < 3:
                with self._persist_retry_lock:
                    if len(self._pending_persist_retries) < 100:
                        self._pending_persist_retries.append((confirmed_candidates, frame_idx, attempt + 1))
        finally:
            db.close()

    def get_runtime_status(self) -> Dict[str, Any]:
        uptime = round(time.time() - self.start_time, 1)
        last_dt = datetime.fromtimestamp(self.last_frame_time, tz=timezone.utc).isoformat() if self.last_frame_time else None
        return {
            'camera_id': self.camera_id,
            'tenant_id': self.tenant_id,
            'status': self.status,
            'received_fps': self.received_fps,
            'processed_fps': self.processed_fps,
            'received_frames': self.received_frames,
            'processed_frames': self.processed_frames,
            'active_tracks': self.active_tracks_count,
            'reconnect_count': self.reconnect_count,
            'last_frame_time': last_dt,
            'last_error': self.last_error,
            'uptime_seconds': uptime,
            'consumer_count': self.consumer_count,
            'sanitized_url': sanitize_stream_url(self.stream_url),
            'persistence_stats': {
                'success_count': self.persistence_success_count,
                'failure_count': self.persistence_failure_count,
                'pending_retries': len(self._pending_persist_retries)
            },
            'latency_summary': {
                'frame_age_ms': self._latest_metadata.get('frame_age_ms', 0.0),
                'inference_duration_ms': self._latest_metadata.get('inference_duration_ms', 0.0),
                'persistence_duration_ms': self._latest_metadata.get('persistence_duration_ms', 0.0),
                'jpeg_encode_ms': self._latest_metadata.get('jpeg_encode_ms', 0.0),
                'server_pipeline_latency_ms': self._latest_metadata.get('server_pipeline_latency_ms', 0.0)
            },
            'policy_id': getattr(settings, 'ACTIVE_POLICY_ID', 'POL-ALERTING-V1'),
            'operating_tau': float(self.analyzer.score_threshold),
            'operating_margin': float(self.analyzer.contrast_margin),
            'camera_profile': 'C5_PHOTOMETRIC' if getattr(self, 'is_c5_profile', False) else 'DEFAULT'
        }

    def record_client_latency(self, frame_idx: int, capture_timestamp: float, display_timestamp: float, display_latency_ms: float):
        with self._lock:
            self._client_latency_samples.append({
                'frame_idx': frame_idx,
                'capture_timestamp': capture_timestamp,
                'display_timestamp': display_timestamp,
                'display_latency_ms': display_latency_ms
            })

    def get_latency_statistics(self) -> Dict[str, Any]:
        with self._lock:
            server_samples = list(self._latency_samples)
            client_samples = list(self._client_latency_samples)

        def _calc_stats(vals: List[float]) -> Dict[str, Any]:
            if not vals:
                return {'count': 0, 'median_ms': None, 'p95_ms': None, 'p99_ms': None, 'min_ms': None, 'max_ms': None}
            arr = np.array(vals, dtype=np.float64)
            return {
                'count': len(vals),
                'median_ms': round(float(np.median(arr)), 2),
                'p95_ms': round(float(np.percentile(arr, 95)), 2),
                'p99_ms': round(float(np.percentile(arr, 99)), 2),
                'min_ms': round(float(np.min(arr)), 2),
                'max_ms': round(float(np.max(arr)), 2)
            }

        return {
            'camera_id': self.camera_id,
            'total_server_samples': len(server_samples),
            'total_client_samples': len(client_samples),
            'frame_age': _calc_stats([s['frame_age_ms'] for s in server_samples]),
            'inference_duration': _calc_stats([s['inference_duration_ms'] for s in server_samples]),
            'persistence_duration': _calc_stats([s['persistence_duration_ms'] for s in server_samples]),
            'jpeg_encode': _calc_stats([s['jpeg_encode_ms'] for s in server_samples]),
            'server_pipeline_latency': _calc_stats([s['server_pipeline_latency_ms'] for s in server_samples]),
            'actual_browser_display_latency': _calc_stats([s['display_latency_ms'] for s in client_samples]),
            'definitions': {
                'frame_age_ms': 'Time elapsed between camera capture and acquisition by inference worker',
                'inference_duration_ms': 'Execution duration of person detection and Re-ID feature extraction',
                'persistence_duration_ms': 'Database passage event persistence execution duration',
                'jpeg_encode_ms': 'In-memory JPEG HUD rendering and compression duration',
                'server_pipeline_latency_ms': 'Sum of frame age + inference + persistence + JPEG encode',
                'actual_browser_display_latency_ms': 'Direct client measurement: requestAnimationFrame render time minus capture timestamp'
            }
        }

    def generate_mjpeg_stream(self, is_revoked_fn: Optional[Callable[[], bool]] = None) -> Generator[bytes, None, None]:
        with self._lock:
            self.consumer_count += 1
        last_sent_idx = -1
        try:
            while not self._stop_event.is_set():
                if is_revoked_fn and is_revoked_fn():
                    break
                frame_bytes = None
                meta = None
                with self._new_annotated_cond:
                    while not self._stop_event.is_set():
                        if is_revoked_fn and is_revoked_fn():
                            break
                        curr_idx = self._latest_metadata.get('frame_idx', -1)
                        if curr_idx > last_sent_idx and self._latest_jpeg is not None:
                            frame_bytes = self._latest_jpeg
                            meta = dict(self._latest_metadata)
                            last_sent_idx = curr_idx
                            break
                        if not self._new_annotated_cond.wait(timeout=0.3):
                            break

                if self._stop_event.is_set() or (is_revoked_fn and is_revoked_fn()):
                    break

                if frame_bytes is not None and meta is not None:
                    cap_ts = meta.get('capture_timestamp', 0.0)
                    inf_ms = meta.get('inference_duration_ms', 0.0)
                    enc_ms = meta.get('jpeg_encode_ms', 0.0)
                    f_idx = meta.get('frame_idx', 0)
                    server_mono_ms = time.perf_counter() * 1000.0
                    headers = (
                        f"--frame\r\n"
                        f"Content-Type: image/jpeg\r\n"
                        f"X-Capture-Timestamp: {cap_ts:.6f}\r\n"
                        f"X-Inference-Duration-Ms: {inf_ms:.2f}\r\n"
                        f"X-Encoding-Duration-Ms: {enc_ms:.2f}\r\n"
                        f"X-Server-Monotonic-Ms: {server_mono_ms:.2f}\r\n"
                        f"X-Frame-Index: {f_idx}\r\n\r\n"
                    ).encode('ascii')
                    yield headers + frame_bytes + b'\r\n'
        finally:
            with self._lock:
                self.consumer_count = max(0, self.consumer_count - 1)


class CameraStreamManager:

    def __init__(self):
        self._workers: Dict[str, LiveCameraStreamWorker] = {}
        self._lock = threading.Lock()

    def get_worker(self, camera_id: str) -> Optional[LiveCameraStreamWorker]:
        with self._lock:
            return self._workers.get(camera_id)

    def start_camera_stream(self, tenant_id: str, camera_id: str, stream_url: Optional[str] = None, user_id: Optional[str] = None, is_loop: bool = False, db: Optional[Session] = None) -> LiveCameraStreamWorker:
        with self._lock:
            existing = self._workers.get(camera_id)
            if existing and existing.status in ('ONLINE', 'CONNECTING', 'DEGRADED'):
                return existing

            url_to_use = stream_url
            target_fps = 25.0
            if not url_to_use:
                session_to_use = db
                close_db = False
                if session_to_use is None:
                    session_to_use = SessionLocal()
                    close_db = True
                try:
                    cam = session_to_use.execute(select(Camera).where(Camera.tenant_id == tenant_id, Camera.id == camera_id)).scalar_one_or_none()
                    if not cam or not cam.rtsp_url_encrypted:
                        raise ValueError(f"Camera '{camera_id}' has no configured RTSP URL.")
                    url_to_use = decrypt_secret(cam.rtsp_url_encrypted)
                    target_fps = cam.stream_fps
                finally:
                    if close_db:
                        session_to_use.close()

            worker = LiveCameraStreamWorker(
                tenant_id=tenant_id,
                camera_id=camera_id,
                stream_url=url_to_use,
                stream_fps=target_fps,
                is_loop=is_loop,
                db=db
            )
            worker.start()
            self._workers[camera_id] = worker

        log_db = db
        close_log_db = False
        if log_db is None:
            log_db = SessionLocal()
            close_log_db = True
        try:
            log_audit_event(
                db=log_db,
                action='START_CAMERA_STREAM',
                entity_type='CAMERA',
                entity_id=camera_id,
                tenant_id=tenant_id,
                user_id=user_id,
                details={'url': sanitize_stream_url(url_to_use)}
            )
        finally:
            if close_log_db:
                log_db.close()

        return worker

    def stop_camera_stream(self, camera_id: str, user_id: Optional[str] = None, db: Optional[Session] = None) -> bool:
        worker = None
        with self._lock:
            worker = self._workers.pop(camera_id, None)

        if not worker:
            return False

        worker.stop()

        log_db = db
        close_log_db = False
        if log_db is None:
            log_db = SessionLocal()
            close_log_db = True
        try:
            log_audit_event(
                db=log_db,
                action='STOP_CAMERA_STREAM',
                entity_type='CAMERA',
                entity_id=camera_id,
                tenant_id=worker.tenant_id,
                user_id=user_id
            )
        finally:
            if close_log_db:
                log_db.close()

        return True


    def get_status(self, camera_id: str) -> Optional[Dict[str, Any]]:
        worker = self.get_worker(camera_id)
        if worker:
            return worker.get_runtime_status()
        return None

    def get_latency(self, camera_id: str) -> Optional[Dict[str, Any]]:
        worker = self.get_worker(camera_id)
        if worker:
            return worker.get_latency_statistics()
        return None

    def record_client_latency(self, camera_id: str, frame_idx: int, capture_timestamp: float, display_timestamp: float, display_latency_ms: float) -> bool:
        worker = self.get_worker(camera_id)
        if worker:
            worker.record_client_latency(frame_idx, capture_timestamp, display_timestamp, display_latency_ms)
            return True
        return False

    def test_connectivity(self, stream_url: str, timeout_seconds: float = 5.0) -> Dict[str, Any]:
        sanitized = sanitize_stream_url(stream_url)
        try:
            validate_stream_url(stream_url)
        except Exception as exc:
            return {'success': False, 'error': f"Validation rejected for '{sanitized}': {str(exc)}"}

        if os.path.isfile(stream_url):
            cap = cv2.VideoCapture(stream_url)
        else:
            os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"
            timeout_ms = int(timeout_seconds * 1000)
            cap = cv2.VideoCapture(
                stream_url,
                cv2.CAP_FFMPEG,
                [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, timeout_ms, cv2.CAP_PROP_READ_TIMEOUT_MSEC, timeout_ms]
            )

        t_start = time.time()
        connected = False
        w, h, fps = 0, 0, 0.0

        try:
            while time.time() - t_start < timeout_seconds:
                if cap.isOpened():
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        connected = True
                        h, w = frame.shape[:2]
                        fps = float(cap.get(cv2.CAP_PROP_FPS) or 25.0)
                        break
                time.sleep(0.1)
        finally:
            cap.release()

        if connected:
            return {
                'success': True,
                'width': w,
                'height': h,
                'fps': round(fps, 1),
                'message': f"Stream verified: {w}x{h} @ {fps:.1f} FPS"
            }
        return {
            'success': False,
            'error': f"Could not connect to RTSP stream '{sanitized}' within {timeout_seconds:.1f}s timeout."
        }

    def shutdown_all(self):
        with self._lock:
            all_workers = list(self._workers.values())
            self._workers.clear()
        for w in all_workers:
            try:
                w.stop(timeout=1.5)
            except Exception:
                pass

stream_manager = CameraStreamManager()
