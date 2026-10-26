from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from .models import PortableModel

CTL_SCHEMA_VERSION = "ctl-0.1"
TransitionMechanism = Literal["hard_cut", "motion_peak_cut"]


class CtlClip(PortableModel):
    id: str
    asset_id: str
    shot_id: str
    source_in_seconds: float = Field(ge=0)
    source_out_seconds: float = Field(gt=0)
    timeline_in_seconds: float = Field(ge=0)
    timeline_out_seconds: float = Field(gt=0)

    @model_validator(mode="after")
    def validate_ranges(self) -> "CtlClip":
        if self.source_out_seconds <= self.source_in_seconds:
            raise ValueError("CTL source range must have positive duration")
        if self.timeline_out_seconds <= self.timeline_in_seconds:
            raise ValueError("CTL timeline range must have positive duration")
        return self


class CtlTransition(PortableModel):
    boundary_index: int = Field(ge=1)
    mechanism: TransitionMechanism
    duration_seconds: float = Field(default=0, ge=0)
    reason: str


class CtlProgram(PortableModel):
    schema_version: str = CTL_SCHEMA_VERSION
    project_id: str
    duration_seconds: float = Field(gt=0)
    clips: list[CtlClip]
    transitions: list[CtlTransition]
    render_fps: int = Field(default=24, ge=1, le=120)
    render_width: int = Field(default=960, ge=320)
