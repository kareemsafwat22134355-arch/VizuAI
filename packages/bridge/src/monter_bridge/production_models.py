from __future__ import annotations

from typing import Literal

from pydantic import Field

from .models import PortableModel

ProductionStatus = Literal["pass", "needs_review"]


class ProductionReport(PortableModel):
    project_id: str
    status: ProductionStatus
    revision_iterations: int = Field(ge=0)
    assets_ingested: int = Field(ge=0)
    shots_analyzed: int = Field(ge=0)
    edit_segments: int = Field(ge=0)
    target_duration_seconds: float = Field(gt=0)
    actual_duration_seconds: float = Field(gt=0)
    artifacts: list[str]
    warnings: list[str] = Field(default_factory=list)
