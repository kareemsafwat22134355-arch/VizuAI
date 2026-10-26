from __future__ import annotations

from typing import Literal

from pydantic import Field

from .models import PortableModel

RENDER_ANALYSIS_SCHEMA_VERSION = "render-analysis-0.1"
RenderAnalysisStatus = Literal["pass", "needs_review"]
FindingSeverity = Literal["info", "warning", "error"]


class RenderEnergyBin(PortableModel):
    index: int = Field(ge=0)
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(gt=0)
    mean_motion: float = Field(ge=0, le=1)
    mean_luma: float = Field(ge=0, le=1)
    black_fraction: float = Field(ge=0, le=1)
    freeze_fraction: float = Field(ge=0, le=1)
    target_energy: float = Field(ge=0, le=1)


class RenderAnalysisFinding(PortableModel):
    code: str
    severity: FindingSeverity
    message: str


class RenderAnalysisReport(PortableModel):
    schema_version: str = RENDER_ANALYSIS_SCHEMA_VERSION
    project_id: str
    path_label: str
    status: RenderAnalysisStatus
    duration_seconds: float = Field(ge=0)
    expected_duration_seconds: float = Field(gt=0)
    duration_drift_seconds: float
    has_audio: bool
    sampled_frames: int = Field(ge=0)
    mean_motion: float = Field(ge=0, le=1)
    peak_motion: float = Field(ge=0, le=1)
    black_frame_fraction: float = Field(ge=0, le=1)
    freeze_pair_fraction: float = Field(ge=0, le=1)
    longest_freeze_seconds: float = Field(ge=0)
    energy_alignment: float = Field(ge=0, le=1)
    energy_bins: list[RenderEnergyBin]
    findings: list[RenderAnalysisFinding]
    notes: list[str] = Field(default_factory=list)
