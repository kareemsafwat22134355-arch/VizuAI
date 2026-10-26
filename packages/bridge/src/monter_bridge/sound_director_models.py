from __future__ import annotations

from typing import Literal

from pydantic import Field

from .audio_edit_models import AudioBoundaryKind
from .models import PortableModel

SOUND_DIRECTOR_SCHEMA_VERSION = "sound-director-0.1"


class AudioWindowMetrics(PortableModel):
    asset_id: str
    source_start_seconds: float = Field(ge=0)
    source_end_seconds: float = Field(gt=0)
    duration_seconds: float = Field(gt=0)
    rms_dbfs: float
    peak_dbfs: float
    active_frame_fraction: float = Field(ge=0, le=1)
    activity_score: float = Field(ge=0, le=1)


class BoundaryAudioEvidence(PortableModel):
    boundary_index: int = Field(ge=1)
    visual_cut_seconds: float = Field(ge=0)
    outgoing_pre: AudioWindowMetrics | None = None
    outgoing_post: AudioWindowMetrics | None = None
    incoming_pre: AudioWindowMetrics | None = None
    incoming_post: AudioWindowMetrics | None = None
    outgoing_handle_seconds: float = Field(ge=0)
    incoming_handle_seconds: float = Field(ge=0)
    blocked_reason: str | None = None


class SoundBoundaryDecision(PortableModel):
    boundary_index: int = Field(ge=1)
    recommendation: AudioBoundaryKind
    overlap_seconds: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    reason: str
    evidence: dict[str, float | str | bool] = Field(default_factory=dict)


class SoundDirectorReport(PortableModel):
    schema_version: str = SOUND_DIRECTOR_SCHEMA_VERSION
    project_id: str
    boundaries: list[BoundaryAudioEvidence] = Field(default_factory=list)
    decisions: list[SoundBoundaryDecision] = Field(default_factory=list)
    selected_intents: list[SoundBoundaryDecision] = Field(default_factory=list)
    max_jl_cuts: int = Field(default=2, ge=0, le=8)
    notes: list[str] = Field(default_factory=list)
