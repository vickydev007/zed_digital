from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.models.tenant import Tenant
from backend.schemas.dashboard import DashboardStatsResponse
from backend.services.dashboard_service import get_dashboard_stats
from backend.api.deps import get_current_tenant

router = APIRouter(prefix='/dashboard', tags=['Dashboard'])

@router.get('/stats', response_model=DashboardStatsResponse)
def get_dashboard_telemetry(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    return get_dashboard_stats(db, current_tenant.id)
