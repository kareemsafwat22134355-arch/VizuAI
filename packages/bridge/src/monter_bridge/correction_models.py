from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Literal

from pydantic import Field, model_validator

from .models import PortableModel

CORRECTION_SCHEMA_VERSION = "human-corrections-0.1"
CorrectionKind = Literal["shot_selection", "trim", "transition", "timewarp", "role", "other"]
CorrectionTargetType = Literal["project", "segment", "boundary"]
CorrectionSource = Literal["cli", "studio", "import", "manual"]
DecisionScalar = str | int | float | bool | None


def _validate_scalar_map(values: dict[str, DecisionScalar], label: str) -> None:
    for key, value in values.items():
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError(f"{label}.{key} must be a finite number")


class HumanCorrection(PortableModel):
    id: str
    kind: CorrectionKind
    target_type: CorrectionTargetType
    target_ref: str | None = None
    ai_decision: dict[str, DecisionScalar]
    human_decision: dict[str, DecisionScalar]
    context: dict[str, DecisionScalar] = Field(default_factory=dict)
    reason: str = Field(min_length=1)
    source: CorrectionSource = "cli"
    created_at: str

    @model_validator(mode="after")
    def validate_target(self) -> "HumanCorrection":
        if self.target_type != "project" and not self.target_ref:
            raise ValueError("segment/boundary corrections require target_ref")
        if self.ai_decision == self.human_decision:
            raise ValueError("human correction must differ from the AI decision")
        _validate_scalar_map(self.ai_decision, "ai_decision")
        _validate_scalar_map(self.human_decision, "human_decision")
        _validate_scalar_map(self.context, "context")
        return self


class CorrectionLedger(PortableModel):
    schema_version: str = CORRECTION_SCHEMA_VERSION
    project_id: str
    created_at: str
    updated_at: str
    corrections: list[HumanCorrection] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=lambda: [
        "Corrections preserve AI decision, human replacement, context and explicit reason.",
        "The ledger is research/evaluation data; corrections are not automatically learned or applied as global style rules.",
    ])

    @classmethod
    def new(cls, project_id: str) -> "CorrectionLedger":
        now = datetime.now(timezone.utc).isoformat()
        return cls(project_id=project_id, created_at=now, updated_at=now)
