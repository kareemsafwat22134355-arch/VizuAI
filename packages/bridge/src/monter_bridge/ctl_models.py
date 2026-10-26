from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from .models import PortableModel

CTL_SCHEMA_VERSION = "ctl-0.1"
TransitionMechanism = Literal["hard_cut", "motion_peak_cut", "motion_match_cut"]
AudioBoundaryMechanism = Literal["straight", "l_cut", "j_cut"]


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
    relation_score: float | None = Field(default=None, ge=0, le=1)
    evidence: dict[str, float | str | bool] = Field(default_factory=dict)
    reason: str


class TimeWarpSlice(PortableModel):
    source_in_seconds: float = Field(ge=0)
    source_out_seconds: float = Field(gt=0)
    playback_rate: float = Field(gt=0.05, le=8)

    @model_validator(mode="after")
    def validate_range(self) -> "TimeWarpSlice":
        if self.source_out_seconds <= self.source_in_seconds:
            raise ValueError("timewarp slice must have positive duration")
        return self


class TimeWarpIntent(PortableModel):
    segment_id: str
    anchor_seconds: float = Field(ge=0)
    reason: str
    slices: list[TimeWarpSlice] = Field(min_length=2)


class AudioBoundaryIntent(PortableModel):
    boundary_index: int = Field(ge=1)
    mechanism: AudioBoundaryMechanism
    offset_seconds: float = Field(default=0.0, ge=0, le=1.0)
    reason: str


class CtlProgram(PortableModel):
    schema_version: str = CTL_SCHEMA_VERSION
    project_id: str
    duration_seconds: float = Field(gt=0)
    clips: list[CtlClip]
    transitions: list[CtlTransition]
    time_warps: list[TimeWarpIntent] = Field(default_factory=list)
    audio_boundaries: list[AudioBoundaryIntent] = Field(default_factory=list)
    source_audio_gain: float = Field(default=0.42, ge=0, le=1.5)
    music_gain: float = Field(default=0.72, ge=0, le=1.5)
    render_fps: int = Field(default=24, ge=1, le=120)
    render_width: int = Field(default=960, ge=320)
