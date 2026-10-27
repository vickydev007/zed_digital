from __future__ import annotations
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.core.config import settings
from backend.core.database import SessionLocal, Base, engine
from backend.services.auth_service import seed_default_admin
from backend.services.evaluation_service import seed_empirical_experiment_run
from backend.services.job_worker import recover_orphaned_jobs
import backend.models

from backend.api.v1.auth import router as auth_router
from backend.api.v1.workers import router as workers_router
from backend.api.v1.cameras import router as cameras_router
from backend.api.v1.videos import router as videos_router
from backend.api.v1.jobs import router as jobs_router
from backend.api.v1.candidates import router as candidates_router
from backend.api.v1.passage import router as passage_router
from backend.api.v1.dashboard import router as dashboard_router
from backend.api.v1.evaluation import router as evaluation_router
from backend.api.v1.media import router as media_router

from sqlalchemy import text, select
from sqlalchemy.orm import Session
from backend.models.video import VideoJob

def ensure_schema_columns():
    with engine.connect() as conn:
        try:
            res = conn.execute(text("PRAGMA table_info(video_jobs)")).fetchall()
            existing_cols = {r[1] for r in res}
            if 'processed_frames' not in existing_cols:
                conn.execute(text("ALTER TABLE video_jobs ADD COLUMN processed_frames INTEGER DEFAULT 0"))
            if 'total_frames' not in existing_cols:
                conn.execute(text("ALTER TABLE video_jobs ADD COLUMN total_frames INTEGER DEFAULT 0"))

            va_res = conn.execute(text("PRAGMA table_info(video_assets)")).fetchall()
            va_cols = {r[1] for r in va_res}
            if 'fps' not in va_cols:
                conn.execute(text("ALTER TABLE video_assets ADD COLUMN fps REAL DEFAULT 25.0"))
            if 'frame_count' not in va_cols:
                conn.execute(text("ALTER TABLE video_assets ADD COLUMN frame_count INTEGER DEFAULT 0"))
            if 'resolution_width' not in va_cols:
                conn.execute(text("ALTER TABLE video_assets ADD COLUMN resolution_width INTEGER DEFAULT 0"))
            if 'resolution_height' not in va_cols:
                conn.execute(text("ALTER TABLE video_assets ADD COLUMN resolution_height INTEGER DEFAULT 0"))

            pe_res = conn.execute(text("PRAGMA table_info(passage_events)")).fetchall()
            pe_cols = {r[1] for r in pe_res}
            if 'policy_id' not in pe_cols:
                conn.execute(text("ALTER TABLE passage_events ADD COLUMN policy_id VARCHAR(64) DEFAULT 'POL-ALERTING-V1'"))

            md_res = conn.execute(text("PRAGMA table_info(match_decisions)")).fetchall()
            md_cols = {r[1] for r in md_res}
            if 'policy_id' not in md_cols:
                conn.execute(text("ALTER TABLE match_decisions ADD COLUMN policy_id VARCHAR(64) DEFAULT 'POL-ALERTING-V1'"))
            conn.commit()
        except Exception:
            pass

def backfill_completed_job_frames(db: Session):
    try:
        jobs = db.execute(select(VideoJob).where(VideoJob.status == 'COMPLETED')).scalars().all()
        for j in jobs:
            if (not j.processed_frames or not j.total_frames) and j.summary_json:
                tf = j.summary_json.get('total_frames_processed', 0)
                if tf:
                    j.processed_frames = tf
                    j.total_frames = tf
        db.commit()
    except Exception:
        db.rollback()

@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(settings.CROPS_DIR, exist_ok=True)
    os.makedirs(settings.OUTPUT_VIDEOS_DIR, exist_ok=True)
    os.makedirs(os.path.join(settings.CROPS_DIR, 'enrollments'), exist_ok=True)
    os.makedirs('experiments/reports', exist_ok=True)

    Base.metadata.create_all(bind=engine)
    ensure_schema_columns()

    db = SessionLocal()
    try:
        recover_orphaned_jobs(db)
        user, tenant = seed_default_admin(db)
        seed_empirical_experiment_run(db, tenant.id)
        backfill_completed_job_frames(db)
    finally:
        db.close()

    yield

    try:
        from backend.services.camera_streamer import stream_manager
        stream_manager.shutdown_all()
    except Exception:
        pass

app = FastAPI(
    title=settings.PROJECT_NAME,
    description='Open-Set Person Re-Identification Under Low Inter-Class Variance Enterprise Backend',
    version='3.5.0',
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

api_v1_prefix = settings.API_V1_PREFIX
app.include_router(auth_router, prefix=api_v1_prefix)
app.include_router(workers_router, prefix=api_v1_prefix)
app.include_router(cameras_router, prefix=api_v1_prefix)
app.include_router(videos_router, prefix=api_v1_prefix)
app.include_router(jobs_router, prefix=api_v1_prefix)
app.include_router(candidates_router, prefix=api_v1_prefix)
app.include_router(passage_router, prefix=api_v1_prefix)
app.include_router(dashboard_router, prefix=api_v1_prefix)
app.include_router(evaluation_router, prefix=api_v1_prefix)
app.include_router(media_router, prefix=api_v1_prefix)

@app.get('/health', tags=['Health'])
def health_check():
    return {
        'status': 'healthy',
        'project': settings.PROJECT_NAME,
        'version': '3.5.0',
        'active_policy_id': settings.ACTIVE_POLICY_ID,
        'operating_tau': settings.DEFAULT_SCORE_THRESHOLD,
        'operating_margin': settings.DEFAULT_CONTRAST_MARGIN,
        'operating_min_obs': settings.DEFAULT_MIN_OBSERVATIONS
    }

@app.get('/policies', tags=['Policies'])
def get_operational_policies():
    from openset_reid.open_set.policies import list_policies, get_policy
    active = get_policy(settings.ACTIVE_POLICY_ID)
    return {
        'active_policy_id': settings.ACTIVE_POLICY_ID,
        'active_policy': active.to_dict(),
        'all_policies': list_policies()
    }

@app.get('/', tags=['Root'])
def root():
    return {
        'message': 'Open-Set Person Re-Identification Platform Backend API',
        'docs_url': '/docs',
        'openapi_url': '/openapi.json',
        'api_version': 'v1',
        'active_policy_id': settings.ACTIVE_POLICY_ID
    }

