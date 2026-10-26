from __future__ import annotations

from datetime import datetime, timezone

from pydantic import Field

from .cut_signature import CutSignature
from .models import PortableModel

MICROSCOPE_SCHEMA_VERSION = "microscope-0.1"
STYLE_PROFILE_SCHEMA_VERSION = "style-profile-0.1"


class ObservedCut(PortableModel):
    index: int = Field(ge=1)
    time_seconds: float = Field(ge=0)
    left_shot_id: str
    right_shot_id: str
    left_duration_seconds: float = Field(gt=0)
    right_duration_seconds: float = Field(gt=0)
    signature: CutSignature
    classification: str


class MicroscopeReport(PortableModel):
    schema_version: str = MICROSCOPE_SCHEMA_VERSION
    source_label: str
    source_duration_seconds: float = Field(gt=0)
    created_at: str
    shot_count: int = Field(ge=1)
    cut_count: int = Field(ge=0)
    shot_durations_seconds: list[float]
    mean_shot_duration_seconds: float = Field(gt=0)
    median_shot_duration_seconds: float = Field(gt=0)
    p25_shot_duration_seconds: float = Field(gt=0)
    p75_shot_duration_seconds: float = Field(gt=0)
    fast_cut_rate: float = Field(ge=0, le=1)
    long_hold_rate: float = Field(ge=0, le=1)
    direction_continuity_rate: float = Field(ge=0, le=1)
    action_phase_cut_rate: float = Field(ge=0, le=1)
    deliberate_discontinuity_rate: float = Field(ge=0, le=1)
    motion_match_opportunity_rate: float = Field(ge=0, le=1)
    median_relation_score: float = Field(ge=0, le=1)
    motion_energy_arc: list[float]
    direction_distribution: dict[str, float]
    cuts: list[ObservedCut]
    limitations: list[str]

    @classmethod
    def empty_metadata(cls, source_label: str, duration: float) -> dict[str, object]:
        return {
            "source_label": source_label,
            "source_duration_seconds": duration,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }


class StyleProfile(PortableModel):
    schema_version: str = STYLE_PROFILE_SCHEMA_VERSION
    profile_name: str
    created_at: str
    source_labels: list[str]
    videos_analyzed: int = Field(ge=1)
    cuts_analyzed: int = Field(ge=0)
    mean_shot_duration_seconds: float = Field(gt=0)
    median_shot_duration_seconds: float = Field(gt=0)
    fast_cut_rate: float = Field(ge=0, le=1)
    long_hold_rate: float = Field(ge=0, le=1)
    direction_continuity_rate: float = Field(ge=0, le=1)
    action_phase_cut_rate: float = Field(ge=0, le=1)
    deliberate_discontinuity_rate: float = Field(ge=0, le=1)
    motion_match_opportunity_rate: float = Field(ge=0, le=1)
    median_relation_score: float = Field(ge=0, le=1)
    normalized_energy_arc: list[float]
    direction_distribution: dict[str, float]
    confidence: float = Field(ge=0, le=1)
    interpretation: list[str]
    limitations: list[str]
