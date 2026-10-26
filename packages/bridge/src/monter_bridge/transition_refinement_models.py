from __future__ import annotations

from typing import Literal

from pydantic import Field

from .models import PortableModel
from .transition_opportunities import TransitionOpportunityMechanism

REFINEMENT_SCHEMA_VERSION = "transition-refinement-0.1"
RefinementStatus = Literal["confirmed", "demoted", "unchanged", "unresolved"]


class BoundaryTransitionRefinement(PortableModel):
    boundary_index: int = Field(ge=1)
    base_mechanism: TransitionOpportunityMechanism
    refined_mechanism: TransitionOpportunityMechanism
    status: RefinementStatus
    reason: str
    flow_direction_compatibility: float | None = Field(default=None, ge=0, le=1)
    left_directional_coherence: float | None = Field(default=None, ge=0, le=1)
    right_directional_coherence: float | None = Field(default=None, ge=0, le=1)
    evidence: dict[str, float | str | bool] = Field(default_factory=dict)


class TransitionRefinementReport(PortableModel):
    schema_version: str = REFINEMENT_SCHEMA_VERSION
    project_id: str
    boundaries: list[BoundaryTransitionRefinement] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
