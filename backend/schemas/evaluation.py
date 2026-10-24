from __future__ import annotations
from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, ConfigDict

class EvaluationResultItem(BaseModel):
    metric_name: str
    metric_value: float
    confidence_interval_low: Optional[float] = None
    confidence_interval_high: Optional[float] = None
    details_json: Optional[Dict[str, Any]] = None

class ExperimentRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: Optional[str] = None
    experiment_name: str
    model_name: str
    model_version: str
    dataset_split: str
    score_threshold: float
    contrast_margin: float
    evaluation_protocol: str
    metadata_json: Optional[Dict[str, Any]] = None
    created_at: datetime
    results: List[EvaluationResultItem] = []

class BenchmarkSummaryResponse(BaseModel):
    benchmark_id: str
    title: str
    status: str
    empirical_operating_point: Dict[str, Any]
    metrics: Dict[str, float]
    latency: Dict[str, float]
    report_markdown: str
