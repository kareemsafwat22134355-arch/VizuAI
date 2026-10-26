from __future__ import annotations

from typing import Literal

from pydantic import Field

from .models import PortableModel

ADVANCED_RESULTS_SCHEMA_VERSION = "advanced-analysis-results-0.1"
ExecutionStatus = Literal["completed", "backend_unavailable", "failed", "skipped"]


class DenseFlowWindowSummary(PortableModel):
    segment_id: str
    asset_id: str
    shot_id: str
    source_start_seconds: float = Field(ge=0)
    source_end_seconds: float = Field(gt=0)
    sample_count: int = Field(ge=0)
    mean_magnitude: float = Field(ge=0)
    p90_magnitude: float = Field(ge=0)
    mean_dx: float
    mean_dy: float
    directional_coherence: float = Field(ge=0, le=1)


class FeatureExecutionResult(PortableModel):
    feature: Literal["dense_flow", "depth", "segmentation"]
    status: ExecutionStatus
    backend: str
    reason: str
    metrics: dict[str, float | int | str | bool] = Field(default_factory=dict)


class BoundaryExecutionResult(PortableModel):
    boundary_index: int = Field(ge=1)
    priority: float = Field(ge=0, le=1)
    left_flow: DenseFlowWindowSummary | None = None
    right_flow: DenseFlowWindowSummary | None = None
    flow_direction_compatibility: float | None = Field(default=None, ge=0, le=1)
    features: list[FeatureExecutionResult] = Field(default_factory=list)


class AdvancedAnalysisResults(PortableModel):
    schema_version: str = ADVANCED_RESULTS_SCHEMA_VERSION
    project_id: str
    boundaries: list[BoundaryExecutionResult] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
