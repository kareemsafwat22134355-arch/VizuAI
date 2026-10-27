from __future__ import annotations

from typing import Literal

from pydantic import Field

from .models import PortableModel

FINAL_CRITIC_SCHEMA_VERSION = "final-critic-0.1"
FinalCriticStatus = Literal["pass", "needs_revision", "needs_review"]
FindingDomain = Literal["editorial", "render_integrity", "audio_integrity"]
Reviseability = Literal["automatic_candidate", "manual_only", "not_applicable"]
Severity = Literal["info", "warning", "error"]


class FinalCriticFinding(PortableModel):
    code: str
    domain: FindingDomain
    severity: Severity
    reviseability: Reviseability
    message: str
    source_artifact: str
    segment_id: str | None = None
    boundary_index: int | None = None
    suggested_shift_seconds: float | None = None


class FinalCriticMetric(PortableModel):
    name: str
    domain: FindingDomain
    value: float
    target: str
    passed: bool


class FinalCriticReport(PortableModel):
    schema_version: str = FINAL_CRITIC_SCHEMA_VERSION
    project_id: str
    status: FinalCriticStatus
    automatic_revision_candidates: int = Field(default=0, ge=0)
    manual_review_findings: int = Field(default=0, ge=0)
    metrics: list[FinalCriticMetric]
    findings: list[FinalCriticFinding]
    notes: list[str] = Field(default_factory=list)
