from __future__ import annotations

from pydantic import Field

from .models import PortableModel

POST_RENDER_REVISION_SCHEMA_VERSION = "post-render-revision-0.1"


class PostRenderRevisionReport(PortableModel):
    schema_version: str = POST_RENDER_REVISION_SCHEMA_VERSION
    project_id: str
    eligible: bool
    attempted: bool
    changed: bool
    accepted: bool
    reason: str
    baseline_final_status: str
    candidate_final_status: str | None = None
    baseline_automatic_candidates: int = Field(default=0, ge=0)
    candidate_automatic_candidates: int | None = Field(default=None, ge=0)
    changed_segments: list[str] = Field(default_factory=list)
    changed_boundaries: list[int] = Field(default_factory=list)
    candidate_dir: str | None = None
    baseline_snapshot_dir: str | None = None
    promoted_artifacts: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
