from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from .analysis_models import OcclusionEdge
from .models import PortableModel

ADVANCED_ANALYSIS_SCHEMA_VERSION = "advanced-analysis-plan-0.2"
AdvancedFeature = Literal["dense_flow", "depth", "segmentation"]
SegmentationPromptSide = Literal["left", "right"]
SegmentationPromptKind = Literal["point_and_box"]


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


class SegmentationPromptContext(PortableModel):
    side: SegmentationPromptSide
    prompt_kind: SegmentationPromptKind = "point_and_box"
    source_time_seconds: float = Field(ge=0)
    point_xy_norm: list[float] = Field(min_length=2, max_length=2)
    box_xyxy_norm: list[float] = Field(min_length=4, max_length=4)
    confidence: float = Field(ge=0, le=1)
    occlusion_score: float = Field(ge=0, le=1)
    dominant_edge: OcclusionEdge = "none"
    provenance: Literal["camera_compensated_largest_residual_component"] = (
        "camera_compensated_largest_residual_component"
    )

    @model_validator(mode="after")
    def validate_normalized_geometry(self) -> "SegmentationPromptContext":
        values = [*self.point_xy_norm, *self.box_xyxy_norm]
        if any(value < 0.0 or value > 1.0 for value in values):
            raise ValueError("segmentation prompt coordinates must be normalized to [0, 1]")
        x1, y1, x2, y2 = self.box_xyxy_norm
        if x2 <= x1 or y2 <= y1:
            raise ValueError("segmentation prompt box must have positive normalized area")
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
