from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Literal

from pydantic import Field, model_validator

from .correction_models import CorrectionKind, CorrectionSource, CorrectionTargetType, DecisionScalar
from .models import PortableModel

REVIEW_SCHEMA_VERSION = "decision-reviews-0.1"
REVIEW_SUMMARY_SCHEMA_VERSION = "decision-review-summary-0.1"
ReviewOutcome = Literal["accepted", "corrected"]


def _validate_scalar_map(values: dict[str, DecisionScalar], label: str) -> None:
    for key, value in values.items():
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError(f"{label}.{key} must be a finite number")


class DecisionReview(PortableModel):
    id: str
    kind: CorrectionKind
    target_type: CorrectionTargetType
    target_ref: str | None = None
    ai_decision: dict[str, DecisionScalar]
    outcome: ReviewOutcome
    correction_id: str | None = None
    context: dict[str, DecisionScalar] = Field(default_factory=dict)
    reason: str = Field(min_length=1)
    source: CorrectionSource = "cli"
    created_at: str

    @model_validator(mode="after")
    def validate_review(self) -> "DecisionReview":
        if self.target_type != "project" and not self.target_ref:
            raise ValueError("segment/boundary reviews require target_ref")
        if self.outcome == "accepted" and self.correction_id is not None:
            raise ValueError("accepted review cannot reference a correction")
        if self.outcome == "corrected" and not self.correction_id:
            raise ValueError("corrected review requires correction_id")
        _validate_scalar_map(self.ai_decision, "ai_decision")
        _validate_scalar_map(self.context, "context")
        return self


class DecisionReviewLedger(PortableModel):
    schema_version: str = REVIEW_SCHEMA_VERSION
    project_id: str
    created_at: str
    updated_at: str
    reviews: list[DecisionReview] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=lambda: [
        "A review records every human-inspected AI decision, including accepted decisions.",
        "Corrected reviews reference human-corrections.json instead of duplicating the replacement decision.",
        "Review rates are descriptive evidence only and are not automatically promoted into planner policy.",
    ])

    @classmethod
    def new(cls, project_id: str) -> "DecisionReviewLedger":
        now = datetime.now(timezone.utc).isoformat()
        return cls(project_id=project_id, created_at=now, updated_at=now)


class ReviewBucket(PortableModel):
    reviewed: int = Field(ge=0)
    accepted: int = Field(ge=0)
    corrected: int = Field(ge=0)
    acceptance_rate: float = Field(ge=0, le=1)


class DecisionReviewSummary(PortableModel):
    schema_version: str = REVIEW_SUMMARY_SCHEMA_VERSION
    project_id: str
    generated_at: str
    reviewed: int = Field(ge=0)
    accepted: int = Field(ge=0)
    corrected: int = Field(ge=0)
    acceptance_rate: float = Field(ge=0, le=1)
    by_kind: dict[str, ReviewBucket] = Field(default_factory=dict)
    by_director_role: dict[str, ReviewBucket] = Field(default_factory=dict)
    by_transition_mechanism: dict[str, ReviewBucket] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)

    @classmethod
    def empty(cls, project_id: str) -> "DecisionReviewSummary":
        return cls(
            project_id=project_id,
            generated_at=datetime.now(timezone.utc).isoformat(),
            reviewed=0,
            accepted=0,
            corrected=0,
            acceptance_rate=0.0,
            notes=["No reviewed decisions are available yet."],
        )
