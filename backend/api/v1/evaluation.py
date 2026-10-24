from __future__ import annotations
from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.models.tenant import Tenant, User
from backend.schemas.evaluation import BenchmarkSummaryResponse, ExperimentRunResponse
from backend.services.evaluation_service import (
    get_benchmark_summary,
    list_experiment_runs,
    seed_empirical_experiment_run
)
from backend.api.deps import get_current_tenant, get_current_user

router = APIRouter(prefix='/evaluation', tags=['Evaluation & Benchmarks'])

@router.get('/benchmarks', response_model=BenchmarkSummaryResponse)
def get_empirical_benchmarks():
    return get_benchmark_summary()

@router.get('/experiments', response_model=List[ExperimentRunResponse])
def get_experiments(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    runs = list_experiment_runs(db, current_tenant.id)
    return [ExperimentRunResponse.model_validate(r) for r in runs]

@router.post('/experiments/seed', response_model=ExperimentRunResponse, status_code=status.HTTP_201_CREATED)
def seed_benchmark_run(
    current_tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    run = seed_empirical_experiment_run(db, current_tenant.id)
    return ExperimentRunResponse.model_validate(run)
