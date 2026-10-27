from __future__ import annotations

from typing import Literal

from pydantic import Field

from .models import PortableModel

Severity = Literal["info", "warning", "error"]
CriticStatus = Literal["pass", "needs_revision"]
RevisionKind = Literal[
    "replace_segment",
    "realign_boundary",
    "roll_boundary",
    "review_duration",
    "review_transition",
    "review_analysis",
]
RevisionVerificationKind = Literal["advanced_action_timing"]


class CriticMetric(PortableModel):
    name: str
    value: float
    target: str
    passed: bool


class CriticFinding(PortableModel):
    code: str
    severity: Severity
    message: str
    segment_id: str | None = None
    boundary_index: int | None = None
    suggested_shift_seconds: float | None = None


class CriticReport(PortableModel):
    project_id: str
    status: CriticStatus
    metrics: list[CriticMetric]
    findings: list[CriticFinding]
    notes: list[str] = Field(default_factory=list)


class RevisionAction(PortableModel):
    kind: RevisionKind
    reason: str
    segment_id: str | None = None
    boundary_index: int | None = None
    from_shot_id: str | None = None
    to_shot_id: str | None = None
    left_shift_seconds: float | None = None
    right_shift_seconds: float | None = None
    boundary_shift_seconds: float | None = None
    verification_kind: RevisionVerificationKind | None = None


class RevisionReport(PortableModel):
    project_id: str
    changed: bool
    actions: list[RevisionAction]
