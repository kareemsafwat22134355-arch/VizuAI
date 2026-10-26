from __future__ import annotations

from typing import Literal

from pydantic import Field

from .models import PortableModel

ProductionStatus = Literal["pass", "needs_review"]


class ProductionReport(PortableModel):
    project_id: str
    status: ProductionStatus
    revision_iterations: int = Field(ge=0)
    post_render_revision_attempted: bool = False
    post_render_revision_accepted: bool = False
    post_render_revision_count: int = Field(default=0, ge=0, le=1)
    assets_ingested: int = Field(ge=0)
    shots_analyzed: int = Field(ge=0)
    edit_segments: int = Field(ge=0)
    target_duration_seconds: float = Field(gt=0)
    actual_duration_seconds: float = Field(gt=0)
    advanced_pass_executed: bool = False
    advanced_boundaries_executed: int = Field(default=0, ge=0)
    transition_refinements_applied: int = Field(default=0, ge=0)
    sound_pass_executed: bool = False
    sound_non_sync_selected: int = Field(default=0, ge=0)
    audio_mix_audited: bool = False
    audio_mix_safe: bool | None = None
    render_reanalysis_executed: bool = False
    render_integrity_safe: bool | None = None
    render_energy_alignment: float | None = Field(default=None, ge=0, le=1)
    artifacts: list[str]
    warnings: list[str] = Field(default_factory=list)
