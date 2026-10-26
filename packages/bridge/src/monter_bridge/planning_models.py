from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from .models import PortableModel

EditRole = Literal["setup", "promise", "build", "escalate", "rupture", "reveal", "barrage", "vacuum", "payoff"]


class AudioAnalysis(PortableModel):
    duration_seconds: float = Field(ge=0)
    tempo_bpm: float = Field(ge=0)
    beats_seconds: list[float]
    onsets_seconds: list[float]
    rms_mean: float = Field(ge=0)
    rms_peak: float = Field(ge=0)


class DirectorSection(PortableModel):
    role: EditRole
    start_normalized: float = Field(ge=0, le=1)
    end_normalized: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_order(self) -> "DirectorSection":
        if self.end_normalized <= self.start_normalized:
            raise ValueError("director section must have positive duration")
        return self


class DirectorPlan(PortableModel):
    target_duration_seconds: float = Field(gt=0)
    energy_curve: list[float]
    sections: list[DirectorSection]
    restrictions: list[str]


class EditSegment(PortableModel):
    id: str
    asset_id: str
    shot_id: str
    source_in_seconds: float = Field(ge=0)
    source_out_seconds: float = Field(gt=0)
    timeline_in_seconds: float = Field(ge=0)
    timeline_out_seconds: float = Field(gt=0)
    role: EditRole
    target_energy: float = Field(ge=0, le=1)
    shot_energy: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    reason: str

    @model_validator(mode="after")
    def validate_ranges(self) -> "EditSegment":
        if self.source_out_seconds <= self.source_in_seconds:
            raise ValueError("source range must have positive duration")
        if self.timeline_out_seconds <= self.timeline_in_seconds:
            raise ValueError("timeline range must have positive duration")
        return self


class EditPlan(PortableModel):
    project_id: str
    target_duration_seconds: float = Field(gt=0)
    actual_duration_seconds: float = Field(gt=0)
    segments: list[EditSegment]
    strategy_notes: list[str] = Field(default_factory=list)
