from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from .models import PortableModel

AUDIO_EDIT_SCHEMA_VERSION = "audio-edit-plan-0.1"
AudioBoundaryKind = Literal["sync", "j_cut", "l_cut"]


class SourceAudioEvent(PortableModel):
    id: str
    segment_id: str
    asset_id: str
    source_in_seconds: float = Field(ge=0)
    source_out_seconds: float = Field(gt=0)
    timeline_in_seconds: float = Field(ge=0)
    timeline_out_seconds: float = Field(gt=0)
    gain_db: float = Field(default=-3.0, ge=-60, le=12)
    fade_in_seconds: float = Field(default=0.015, ge=0, le=2)
    fade_out_seconds: float = Field(default=0.03, ge=0, le=2)
    reason: str

    @model_validator(mode="after")
    def validate_ranges(self) -> "SourceAudioEvent":
        source_duration = self.source_out_seconds - self.source_in_seconds
        timeline_duration = self.timeline_out_seconds - self.timeline_in_seconds
        if source_duration <= 0 or timeline_duration <= 0:
            raise ValueError("source-audio event ranges must have positive duration")
        if abs(source_duration - timeline_duration) > 0.005:
            raise ValueError("v0.19 source-audio events require 1x playback; source and timeline durations must match")
        if self.fade_in_seconds + self.fade_out_seconds > timeline_duration + 1e-6:
            raise ValueError("source-audio fades cannot exceed event duration")
        return self


class AudioBoundaryIntent(PortableModel):
    boundary_index: int = Field(ge=1)
    kind: AudioBoundaryKind
    overlap_seconds: float = Field(default=0, ge=0, le=1)
    reason: str

    @model_validator(mode="after")
    def validate_overlap(self) -> "AudioBoundaryIntent":
        if self.kind == "sync" and self.overlap_seconds != 0:
            raise ValueError("sync audio boundaries cannot carry J/L overlap")
        if self.kind in {"j_cut", "l_cut"} and self.overlap_seconds <= 0:
            raise ValueError("J/L cuts require positive overlap")
        return self


class AudioEditPlan(PortableModel):
    schema_version: str = AUDIO_EDIT_SCHEMA_VERSION
    project_id: str
    duration_seconds: float = Field(gt=0)
    events: list[SourceAudioEvent] = Field(default_factory=list)
    boundaries: list[AudioBoundaryIntent] = Field(default_factory=list)
    music_gain_db: float = Field(default=-8.0, ge=-60, le=12)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_timeline_bounds(self) -> "AudioEditPlan":
        for event in self.events:
            if event.timeline_out_seconds > self.duration_seconds + 1e-6:
                raise ValueError(f"source-audio event {event.id} extends beyond audio plan duration")
        seen = [boundary.boundary_index for boundary in self.boundaries]
        if len(seen) != len(set(seen)):
            raise ValueError("audio boundary intents must be unique by boundary_index")
        return self
