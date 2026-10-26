from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import Field, model_validator

from .models import PortableModel

VIR_SCHEMA_VERSION = "vir-0.1"
AnchorType = Literal["clip_start", "clip_end", "motion_onset", "motion_peak", "motion_settle"]


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


class VirProject(PortableModel):
    schema_version: str = VIR_SCHEMA_VERSION
    project_id: str
    created_at: str
    shots: list[ShotAnalysis]
    warnings: list[str] = []

    @classmethod
    def new(cls, project_id: str, shots: list[ShotAnalysis], warnings: list[str] | None = None) -> "VirProject":
        return cls(
            project_id=project_id,
            created_at=datetime.now(timezone.utc).isoformat(),
            shots=shots,
            warnings=warnings or [],
        )
