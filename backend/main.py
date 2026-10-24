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

@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(settings.CROPS_DIR, exist_ok=True)
    os.makedirs(settings.OUTPUT_VIDEOS_DIR, exist_ok=True)
    os.makedirs(os.path.join(settings.CROPS_DIR, 'enrollments'), exist_ok=True)
    os.makedirs('experiments/reports', exist_ok=True)

    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        recover_orphaned_jobs(db)
        user, tenant = seed_default_admin(db)
        seed_empirical_experiment_run(db, tenant.id)
    finally:
        db.close()

    yield

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
        'operating_tau': settings.DEFAULT_SCORE_THRESHOLD,
        'operating_margin': settings.DEFAULT_CONTRAST_MARGIN
    }

@app.get('/', tags=['Root'])
def root():
    return {
        'message': 'Open-Set Person Re-Identification Platform Backend API',
        'docs_url': '/docs',
        'openapi_url': '/openapi.json',
        'api_version': 'v1'
    }
