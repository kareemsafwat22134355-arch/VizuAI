from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from pydantic import BaseModel, Field

SCHEMA_VERSION = "monter-project-0.1"


class MediaTechnical(BaseModel):
    duration_seconds: float = Field(ge=0)
    width: int | None = Field(default=None, ge=1)
    height: int | None = Field(default=None, ge=1)
    fps: float | None = Field(default=None, gt=0)
    codec: str | None = None
    has_audio: bool = False


class MediaAsset(BaseModel):
    id: str
    filename: str
    source_path: str
    source_size_bytes: int = Field(ge=0)
    duration_seconds: float = Field(ge=0)
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    codec: str | None = None
    has_audio: bool = False


class MonterProject(BaseModel):
    schemaVersion: str = SCHEMA_VERSION
    projectId: str
    projectName: str
    createdAt: str
    sourceRootLabel: str
    sourceBytes: int = Field(ge=0)
    proxyBytes: int = Field(default=0, ge=0)
    assets: list[MediaAsset]

    @classmethod
    def new(cls, project_id: str, project_name: str, source_root: Path, assets: list[MediaAsset]) -> "MonterProject":
        return cls(
            projectId=project_id,
            projectName=project_name,
            createdAt=datetime.now(timezone.utc).isoformat(),
            sourceRootLabel=str(source_root),
            sourceBytes=sum(asset.source_size_bytes for asset in assets),
            assets=assets,
        )
