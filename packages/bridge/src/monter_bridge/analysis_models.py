from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import Field, model_validator

from .models import PortableModel

VIR_SCHEMA_VERSION = "vir-0.1"
AnchorType = Literal["clip_start", "clip_end", "motion_onset", "motion_peak", "motion_settle"]
ScreenDirection = Literal["static", "left", "right", "up", "down", "mixed"]
ZoomDirection = Literal["static", "in", "out", "mixed"]
OcclusionEdge = Literal["none", "left", "right", "top", "bottom", "mixed"]


class TimeRange(PortableModel):
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(ge=0)

    @model_validator(mode="after")
    def validate_order(self) -> "TimeRange":
        if self.end_seconds < self.start_seconds:
            raise ValueError("end_seconds must be >= start_seconds")
        return self

    @property
    def duration_seconds(self) -> float:
        return self.end_seconds - self.start_seconds


class MotionSample(PortableModel):
    time_seconds: float = Field(ge=0)
    magnitude: float = Field(ge=0)


class GlobalMotionSample(PortableModel):
    time_seconds: float = Field(ge=0)
    translation_x: float
    translation_y: float
    rotation_degrees: float
    scale: float = Field(gt=0)
    inlier_ratio: float = Field(ge=0, le=1)


class GlobalMotionSummary(PortableModel):
    dominant_screen_direction: ScreenDirection = "static"
    zoom_direction: ZoomDirection = "static"
    mean_translation_x: float = 0.0
    mean_translation_y: float = 0.0
    mean_rotation_degrees: float = 0.0
    mean_scale_delta: float = 0.0
    confidence: float = Field(default=0.0, ge=0, le=1)
    samples: list[GlobalMotionSample] = Field(default_factory=list)


class OcclusionCueSample(PortableModel):
    time_seconds: float = Field(ge=0)
    score: float = Field(ge=0, le=1)
    residual_change_fraction: float = Field(ge=0, le=1)
    largest_component_fraction: float = Field(ge=0, le=1)
    largest_component_bbox_xywh_norm: list[float] | None = Field(default=None, min_length=4, max_length=4)
    largest_component_centroid_xy_norm: list[float] | None = Field(default=None, min_length=2, max_length=2)
    edge_contact_fraction: float = Field(ge=0, le=1)
    dominant_edge: OcclusionEdge = "none"
    compensation_confidence: float = Field(default=0.0, ge=0, le=1)


class OcclusionCueSummary(PortableModel):
    peak_score: float = Field(default=0.0, ge=0, le=1)
    mean_score: float = Field(default=0.0, ge=0, le=1)
    peak_time_seconds: float | None = Field(default=None, ge=0)
    dominant_edge: OcclusionEdge = "none"
    confidence: float = Field(default=0.0, ge=0, le=1)
    samples: list[OcclusionCueSample] = Field(default_factory=list)


class EditAnchor(PortableModel):
    type: AnchorType
    time_seconds: float = Field(ge=0)
    confidence: float = Field(ge=0, le=1)
    reason: str


class ShotAnalysis(PortableModel):
    id: str
    asset_id: str
    range: TimeRange
    mean_motion: float = Field(ge=0)
    peak_motion: float = Field(ge=0)
    motion_samples: list[MotionSample]
    edit_anchors: list[EditAnchor]
    global_motion: GlobalMotionSummary = Field(default_factory=GlobalMotionSummary)
    occlusion: OcclusionCueSummary = Field(default_factory=OcclusionCueSummary)


class VirProject(PortableModel):
    schema_version: str = VIR_SCHEMA_VERSION
    project_id: str
    created_at: str
    shots: list[ShotAnalysis]
    warnings: list[str] = Field(default_factory=list)

    @classmethod
    def new(cls, project_id: str, shots: list[ShotAnalysis], warnings: list[str] | None = None) -> "VirProject":
        return cls(
            project_id=project_id,
            created_at=datetime.now(timezone.utc).isoformat(),
            shots=shots,
            warnings=warnings or [],
        )
