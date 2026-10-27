from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from .models import PortableModel
from .segmentation_prompt_models import SegmentationPromptContext

ADVANCED_ANALYSIS_SCHEMA_VERSION = "advanced-analysis-plan-0.2"
AdvancedFeature = Literal["dense_flow", "depth", "segmentation"]


class SourceAnalysisWindow(PortableModel):
    segment_id: str
    asset_id: str
    shot_id: str
    source_start_seconds: float = Field(ge=0)
    source_end_seconds: float = Field(gt=0)

    @model_validator(mode="after")
    def validate_range(self) -> "SourceAnalysisWindow":
        if self.source_end_seconds <= self.source_start_seconds:
            raise ValueError("advanced analysis window must have positive duration")
        return self


class BoundaryAnalysisRequest(PortableModel):
    boundary_index: int = Field(ge=1)
    priority: float = Field(ge=0, le=1)
    requested_features: list[AdvancedFeature] = Field(min_length=1)
    left_window: SourceAnalysisWindow
    right_window: SourceAnalysisWindow
    left_segmentation_prompt: SegmentationPromptContext | None = None
    right_segmentation_prompt: SegmentationPromptContext | None = None
    reason: str
    evidence: dict[str, float | str | bool] = Field(default_factory=dict)


class SkippedBoundary(PortableModel):
    boundary_index: int = Field(ge=1)
    reason: str


class AdvancedAnalysisPlan(PortableModel):
    schema_version: str = ADVANCED_ANALYSIS_SCHEMA_VERSION
    project_id: str
    max_boundaries: int = Field(ge=1)
    requests: list[BoundaryAnalysisRequest] = Field(default_factory=list)
    skipped_boundaries: list[SkippedBoundary] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
