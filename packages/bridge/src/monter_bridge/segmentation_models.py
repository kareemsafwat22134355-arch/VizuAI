from __future__ import annotations

from typing import Literal

from pydantic import Field

from .models import PortableModel

SEGMENTATION_ARTIFACT_SCHEMA_VERSION = "segmentation-artifact-0.1"
SegmentationSide = Literal["left", "right"]


class SegmentationBackendDescriptor(PortableModel):
    backend_id: str
    backend_version: str
    model_id: str


class SegmentationFrameArtifact(PortableModel):
    time_seconds: float = Field(ge=0)
    mask_path: str
    width: int = Field(ge=1)
    height: int = Field(ge=1)
    foreground_fraction: float = Field(ge=0, le=1)
    bbox_xywh_norm: list[float] | None = Field(default=None, min_length=4, max_length=4)


class SegmentationWindowArtifact(PortableModel):
    schema_version: str = SEGMENTATION_ARTIFACT_SCHEMA_VERSION
    segment_id: str
    asset_id: str
    shot_id: str
    side: SegmentationSide
    source_start_seconds: float = Field(ge=0)
    source_end_seconds: float = Field(gt=0)
    sample_fps: float = Field(gt=0)
    analysis_width: int = Field(ge=64)
    backend: SegmentationBackendDescriptor
    cache_key: str
    cache_hit: bool = False
    frames: list[SegmentationFrameArtifact] = Field(default_factory=list)
