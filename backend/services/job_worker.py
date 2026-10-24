from __future__ import annotations
import os
import time
import uuid
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import cv2
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import select, delete

from backend.core.database import SessionLocal
from backend.core.config import settings
from backend.models.video import VideoJob, VideoAsset
from backend.models.worker import Worker, PersonEmbedding
from backend.models.candidate import CandidateIdentity
from backend.models.tracking import Track, Observation, MatchDecision
from backend.models.passage import PassageEvent, PresenceSession
from backend.models.crop import RepresentativeCrop
from openset_reid.pipeline.video_analyzer import (
    OfflineVideoAnalyzer,
    IdentityStatus,
    PassageStatus,
    PersonCategory,
    resolve_display_category
)

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix='reid_job_worker')
_cancelled_job_ids = set()
_lock = threading.Lock()

def request_job_cancellation(job_id: str):
    with _lock:
        _cancelled_job_ids.add(job_id)

def is_job_cancelled(job_id: str) -> bool:
    with _lock:
        return job_id in _cancelled_job_ids

def recover_orphaned_jobs(db: Optional[Session] = None) -> int:
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True
    try:
        stmt = select(VideoJob).where(VideoJob.status.in_(['RUNNING', 'QUEUED']))
        orphans = list(db.execute(stmt).scalars().all())
        for j in orphans:
            j.status = 'FAILED'
            j.error_details = 'Interrupted by worker or server restart; recovered on startup'
            j.completed_at = datetime.now(timezone.utc)
        if orphans:
            db.commit()
        return len(orphans)
    finally:
        if should_close:
            db.close()

def run_job_execution(job_id: str, options: Dict[str, Any]):
    db: Session = SessionLocal()
    try:
        stmt = select(VideoJob).where(VideoJob.id == job_id)
        job = db.execute(stmt).scalar_one_or_none()
        if not job:
            return
        
        job.status = 'RUNNING'
        job.started_at = datetime.now(timezone.utc)
        job.progress_percent = 5.0
        db.commit()

        tenant_id = job.tenant_id
        video_asset_id = job.video_asset_id
        
        stmt = select(VideoAsset).where(VideoAsset.id == video_asset_id)
        asset = db.execute(stmt).scalar_one_or_none()
        if not asset or not os.path.exists(asset.stored_path):
            job.status = 'FAILED'
            job.error_details = f"Video asset file not found at '{asset.stored_path if asset else None}'"
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
            return

        video_path = asset.stored_path
        score_thresh = float(options.get('score_threshold', settings.DEFAULT_SCORE_THRESHOLD))
        margin = float(options.get('contrast_margin', settings.DEFAULT_CONTRAST_MARGIN))
        max_frames = options.get('max_frames')
        auto_enroll = bool(options.get('auto_enroll_lead_worker', True))

        analyzer = OfflineVideoAnalyzer(
            onnx_model_path=settings.ONNX_MODEL_PATH,
            score_threshold=score_thresh,
            contrast_margin=margin,
            quality_min_h=settings.DEFAULT_QUALITY_MIN_H,
            quality_min_w=settings.DEFAULT_QUALITY_MIN_W,
            quality_min_blur=settings.DEFAULT_QUALITY_MIN_BLUR
        )

        emb_stmt = (
            select(PersonEmbedding, Worker)
            .join(Worker, PersonEmbedding.worker_id == Worker.id)
            .where(
                PersonEmbedding.tenant_id == tenant_id,
                Worker.is_active == True,
                Worker.enrollment_status == 'ENROLLED'
            )
        )
        enrolled_records = db.execute(emb_stmt).all()
        for p_emb, worker in enrolled_records:
            vec = np.array(p_emb.embedding_vector, dtype=np.float32)
            analyzer.matcher.enroll(worker.staff_code, vec)

        out_video_dir = os.path.join(settings.OUTPUT_VIDEOS_DIR, tenant_id)
        os.makedirs(out_video_dir, exist_ok=True)
        out_video_path = os.path.join(out_video_dir, f"{job_id}_annotated.mp4")

        out_crops_dir = os.path.join(settings.CROPS_DIR, tenant_id, job_id)
        os.makedirs(out_crops_dir, exist_ok=True)

        job.output_video_path = out_video_path
        job.output_crops_dir = out_crops_dir
        job.progress_percent = 15.0
        db.commit()

    finally:
        db.close()

    if is_job_cancelled(job_id):
        _finalize_cancelled(job_id)
        return

    try:
        summary = analyzer.analyze_video(
            video_path=video_path,
            output_video_path=out_video_path,
            output_crops_dir=out_crops_dir,
            output_json_path=None,
            max_frames=max_frames,
            auto_enroll_lead_worker=auto_enroll
        )
    except Exception as exc:
        _finalize_failed(job_id, str(exc))
        return

    if is_job_cancelled(job_id):
        _finalize_cancelled(job_id)
        return

    _persist_analysis_results(job_id, tenant_id, summary)

def _finalize_cancelled(job_id: str):
    db: Session = SessionLocal()
    try:
        stmt = select(VideoJob).where(VideoJob.id == job_id)
        job = db.execute(stmt).scalar_one_or_none()
        if job:
            job.status = 'CANCELLED'
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
    finally:
        db.close()
    with _lock:
        _cancelled_job_ids.discard(job_id)

def _finalize_failed(job_id: str, error_message: str):
    db: Session = SessionLocal()
    try:
        stmt = select(VideoJob).where(VideoJob.id == job_id)
        job = db.execute(stmt).scalar_one_or_none()
        if job:
            job.status = 'FAILED'
            job.error_details = error_message[:1000]
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
    finally:
        db.close()
    with _lock:
        _cancelled_job_ids.discard(job_id)

def _persist_analysis_results(job_id: str, tenant_id: str, summary: Dict[str, Any]):
    db: Session = SessionLocal()
    try:
        stmt = select(VideoJob).where(VideoJob.id == job_id)
        job = db.execute(stmt).scalar_one_or_none()
        if not job:
            return

        existing_crops = list(db.execute(select(RepresentativeCrop).join(Track, RepresentativeCrop.track_id == Track.id).where(Track.video_job_id == job.id)).scalars().all())
        for ec in existing_crops:
            db.delete(ec)
        existing_events = list(db.execute(select(PassageEvent).where(PassageEvent.video_job_id == job.id)).scalars().all())
        for ee in existing_events:
            db.delete(ee)
        existing_tracks = list(db.execute(select(Track).where(Track.video_job_id == job.id)).scalars().all())
        for et in existing_tracks:
            db.delete(et)
        db.flush()

        worker_cache: Dict[str, Worker] = {}
        candidate_cache: Dict[int, CandidateIdentity] = {}

        raw_tracks = summary.get('tracks', [])
        for t_info in raw_tracks:
            t_num = t_info['track_id']
            id_status = t_info['identity_status']
            pass_status = t_info['passage_status']
            disp_cat = t_info['display_category']
            matched_code = t_info.get('matched_identity')
            cand_raw_id = t_info.get('candidate_id')
            crop_file = t_info.get('crop_file')

            worker_obj = None
            if id_status == IdentityStatus.OFFICIAL_WORKER.value and matched_code:
                if matched_code not in worker_cache:
                    w_stmt = select(Worker).where(Worker.tenant_id == tenant_id, Worker.staff_code == matched_code)
                    worker_cache[matched_code] = db.execute(w_stmt).scalar_one_or_none()
                worker_obj = worker_cache.get(matched_code)

            cand_obj = None
            if id_status == IdentityStatus.NEW_CANDIDATE.value and cand_raw_id is not None:
                if cand_raw_id not in candidate_cache:
                    cand_code = f"CAND_{job_id[:8]}_{cand_raw_id:03d}"
                    c_stmt = select(CandidateIdentity).where(CandidateIdentity.tenant_id == tenant_id, CandidateIdentity.candidate_code == cand_code)
                    cand_obj = db.execute(c_stmt).scalar_one_or_none()
                    if not cand_obj:
                        cand_obj = CandidateIdentity(
                            tenant_id=tenant_id,
                            candidate_code=cand_code,
                            first_seen_at=datetime.now(timezone.utc),
                            last_seen_at=datetime.now(timezone.utc),
                            review_status='PROVISIONAL',
                            notes=f"Discovered in video job {job_id} track #{t_num}"
                        )
                        db.add(cand_obj)
                        db.flush()
                    candidate_cache[cand_raw_id] = cand_obj
                else:
                    cand_obj = candidate_cache[cand_raw_id]

            track_record = Track(
                tenant_id=tenant_id,
                video_job_id=job.id,
                camera_id=job.video_asset.camera_id if job.video_asset else None,
                track_number=t_num,
                first_frame=t_info.get('first_frame', 0),
                last_frame=t_info.get('last_frame', 0),
                total_seen_frames=t_info.get('seen_frames', 1),
                identity_status=id_status,
                passage_status=pass_status,
                display_category=disp_cat,
                candidate_identity_id=cand_obj.id if cand_obj else None,
                matched_worker_id=worker_obj.id if worker_obj else None
            )
            db.add(track_record)
            db.flush()

            crop_record = None
            if crop_file and os.path.exists(crop_file):
                crop_bgr = cv2.imread(crop_file)
                ch, cw = (crop_bgr.shape[:2]) if crop_bgr is not None else (0, 0)
                crop_record = RepresentativeCrop(
                    tenant_id=tenant_id,
                    track_id=track_record.id,
                    worker_id=worker_obj.id if worker_obj else None,
                    candidate_identity_id=cand_obj.id if cand_obj else None,
                    file_path=crop_file,
                    width=cw,
                    height=ch,
                    retention_status='RETAINED'
                )
                db.add(crop_record)
                db.flush()
                track_record.representative_crop_id = crop_record.id

            event_record = PassageEvent(
                tenant_id=tenant_id,
                camera_id=job.video_asset.camera_id if job.video_asset else None,
                video_job_id=job.id,
                track_id=track_record.id,
                worker_id=worker_obj.id if worker_obj else None,
                candidate_identity_id=cand_obj.id if cand_obj else None,
                identity_status=id_status,
                passage_status=pass_status,
                display_category=disp_cat,
                confidence_score=t_info.get('best_score', 0.0),
                crop_path=crop_file,
                event_timestamp=datetime.now(timezone.utc)
            )
            db.add(event_record)
            db.flush()

            if crop_record:
                crop_record.passage_event_id = event_record.id

            decision_record = MatchDecision(
                tenant_id=tenant_id,
                track_id=track_record.id,
                top_candidate_id=matched_code,
                top_candidate_score=t_info.get('best_score', 0.0),
                runner_up_score=t_info.get('runner_up_score', 0.0),
                score_margin=t_info.get('score_margin', 0.0),
                score_threshold=summary.get('threshold_tau', settings.DEFAULT_SCORE_THRESHOLD),
                contrast_margin=summary.get('contrast_margin', settings.DEFAULT_CONTRAST_MARGIN),
                decision_category=disp_cat,
                is_accepted=(id_status == IdentityStatus.OFFICIAL_WORKER.value),
                rejection_reason=t_info.get('rejection_reason'),
                model_version='v1.0-onnx'
            )
            db.add(decision_record)

            if worker_obj:
                sess_stmt = select(PresenceSession).where(
                    PresenceSession.tenant_id == tenant_id,
                    PresenceSession.worker_id == worker_obj.id,
                    PresenceSession.is_currently_present == True
                )
                active_sess = db.execute(sess_stmt).scalar_one_or_none()
                if active_sess:
                    active_sess.passage_count += 1
                else:
                    new_sess = PresenceSession(
                        tenant_id=tenant_id,
                        worker_id=worker_obj.id,
                        identity_status=id_status,
                        is_currently_present=True,
                        passage_count=1
                    )
                    db.add(new_sess)

        job.status = 'COMPLETED'
        job.progress_percent = 100.0
        job.summary_json = summary
        job.completed_at = datetime.now(timezone.utc)
        db.commit()

    except Exception as exc:
        db.rollback()
        _finalize_failed(job_id, f"Persistence error: {str(exc)}")
    finally:
        db.close()
        with _lock:
            _cancelled_job_ids.discard(job_id)

def enqueue_job_processing(job_id: str, options: Dict[str, Any]):
    _executor.submit(run_job_execution, job_id, options)
