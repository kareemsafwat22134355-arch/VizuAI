from __future__ import annotations

from typing import Literal

from pydantic import Field

from .models import PortableModel

Severity = Literal["info", "warning", "error"]
CriticStatus = Literal["pass", "needs_revision"]
RevisionKind = Literal["replace_segment", "review_duration", "review_transition", "review_analysis"]


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
    from_shot_id: str | None = None
    to_shot_id: str | None = None


class RevisionReport(PortableModel):
    project_id: str
    changed: bool
    actions: list[RevisionAction]
