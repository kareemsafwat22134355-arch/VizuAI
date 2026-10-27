from __future__ import annotations

from pathlib import Path
from typing import Literal

import orjson
from pydantic import Field, model_validator

from .models import PortableModel

SEGMENTATION_BACKEND_CONFIG_SCHEMA_VERSION = "segmentation-backend-config-0.1"
SegmentationBackendId = Literal["none", "sam2"]
SegmentationDevice = Literal["auto", "cpu", "cuda"]


class SegmentationBackendConfig(PortableModel):
    schema_version: str = SEGMENTATION_BACKEND_CONFIG_SCHEMA_VERSION
    backend_id: SegmentationBackendId = "none"
    device: SegmentationDevice = "auto"
    model_id: str | None = None
    checkpoint_path: str | None = None
    model_config_path: str | None = None
    allow_network: bool = False
    parameters: dict[str, str | int | float | bool] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_backend_contract(self) -> "SegmentationBackendConfig":
        if self.allow_network:
            raise ValueError("Network-backed model loading is intentionally disabled; use an explicit local checkpoint")
        if self.backend_id == "none":
            if self.model_id or self.checkpoint_path or self.model_config_path:
                raise ValueError("backendId=none must not carry model/checkpoint configuration")
            return self
        if self.backend_id == "sam2":
            if not self.checkpoint_path or not self.model_config_path:
                raise ValueError("sam2 requires checkpointPath and modelConfigPath; no automatic model download is permitted")
            return self
        raise ValueError(f"Unsupported segmentation backend: {self.backend_id}")


def load_segmentation_backend_config(path: Path) -> SegmentationBackendConfig:
    return SegmentationBackendConfig.model_validate(orjson.loads(path.read_bytes()))
