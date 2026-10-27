from __future__ import annotations

from typing import Literal

from pydantic import Field

from .models import PortableModel
from .segmentation_prompt_models import SegmentationPromptContext

SEGMENTATION_ARTIFACT_SCHEMA_VERSION = "segmentation-artifact-0.2"
SegmentationSide = Literal["left", "right"]
SegmentationExecutionMode = Literal["frame", "window"]
SegmentationParameter = str | int | float | bool


class SegmentationBackendDescriptor(PortableModel):
    backend_id: str
    backend_version: str
    model_id: str
    parameters: dict[str, SegmentationParameter] = Field(default_factory=dict)


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
    execution_mode: SegmentationExecutionMode = "frame"
    prompt_context: SegmentationPromptContext | None = None
    input_digest: str
    cache_key: str
    cache_hit: bool = False
    frames: list[SegmentationFrameArtifact] = Field(default_factory=list)
