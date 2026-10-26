from __future__ import annotations

from pydantic import Field

from .models import PortableModel

AUDIO_MIX_AUDIT_SCHEMA_VERSION = "audio-mix-audit-0.1"


class AudioMixAudit(PortableModel):
    schema_version: str = AUDIO_MIX_AUDIT_SCHEMA_VERSION
    path_label: str
    mean_volume_dbfs: float
    max_volume_dbfs: float
    clipping_safe: bool
    safety_threshold_dbfs: float = Field(default=-0.5, le=0)
    notes: list[str] = Field(default_factory=list)
