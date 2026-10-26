from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

SCHEMA_VERSION = "monter-project-0.1"


class PortableModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class MediaTechnical(PortableModel):
    duration_seconds: float = Field(ge=0)
    width: int | None = Field(default=None, ge=1)
    height: int | None = Field(default=None, ge=1)
    fps: float | None = Field(default=None, gt=0)
    codec: str | None = None
    has_audio: bool = False


class MediaAsset(PortableModel):
    id: str
    filename: str
    source_rel_path: str
    source_size_bytes: int = Field(ge=0)
    duration_seconds: float = Field(ge=0)
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    codec: str | None = None
    has_audio: bool = False


class MonterProject(PortableModel):
    schema_version: str = SCHEMA_VERSION
    project_id: str
    project_name: str
    created_at: str
    source_root_label: str
    source_bytes: int = Field(ge=0)
    proxy_bytes: int = Field(default=0, ge=0)
    assets: list[MediaAsset]

    @classmethod
    def new(cls, project_id: str, project_name: str, source_root: Path, assets: list[MediaAsset]) -> "MonterProject":
        return cls(
            project_id=project_id,
            project_name=project_name,
            created_at=datetime.now(timezone.utc).isoformat(),
            source_root_label=source_root.name or "RAW",
            source_bytes=sum(asset.source_size_bytes for asset in assets),
            assets=assets,
        )
