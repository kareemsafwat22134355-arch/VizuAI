from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from .analysis_models import OcclusionEdge
from .models import PortableModel

SegmentationPromptSide = Literal["left", "right"]
SegmentationPromptKind = Literal["point_and_box"]


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
        point_x, point_y = self.point_xy_norm
        if not (x1 <= point_x <= x2 and y1 <= point_y <= y2):
            raise ValueError("segmentation prompt point must lie inside its normalized box")
        return self
