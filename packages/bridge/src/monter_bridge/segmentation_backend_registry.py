from __future__ import annotations

import importlib.util
from importlib import metadata
from pathlib import Path

from pydantic import Field

from .models import PortableModel
from .segmentation_backend_config import SegmentationBackendConfig


class SegmentationBackendAvailability(PortableModel):
    backend_id: str
    display_name: str
    installed: bool
    configured: bool
    ready: bool
    optional: bool = True
    package_versions: dict[str, str] = Field(default_factory=dict)
    reason: str


def _package_version(name: str) -> str | None:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return None


def _module_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def discover_segmentation_backends() -> list[SegmentationBackendAvailability]:
    torch_present = _module_available("torch")
    sam2_present = _module_available("sam2")
    versions: dict[str, str] = {}
    for package in ("torch", "sam2"):
        version = _package_version(package)
        if version:
            versions[package] = version

    return [
        SegmentationBackendAvailability(
            backend_id="none",
            display_name="Disabled",
            installed=True,
            configured=True,
            ready=True,
            optional=True,
            package_versions={},
            reason="Segmentation is explicitly disabled; MONTER remains fully usable without a heavyweight backend.",
        ),
        SegmentationBackendAvailability(
            backend_id="sam2",
            display_name="Meta SAM 2",
            installed=torch_present and sam2_present,
            configured=False,
            ready=False,
            optional=True,
            package_versions=versions,
            reason=(
                "SAM 2 Python modules are installed; provide an explicit local checkpoint/config to validate readiness."
                if torch_present and sam2_present
                else "Optional SAM 2 runtime is not installed. MONTER will not install or download it automatically."
            ),
        ),
    ]


def validate_segmentation_backend_config(
    config: SegmentationBackendConfig,
) -> SegmentationBackendAvailability:
    discovered = {item.backend_id: item for item in discover_segmentation_backends()}
    baseline = discovered[config.backend_id]

    if config.backend_id == "none":
        return baseline

    checkpoint = Path(config.checkpoint_path or "")
    model_config = Path(config.model_config_path or "")
    files_ready = checkpoint.is_file() and model_config.is_file()
    ready = baseline.installed and files_ready

    if not baseline.installed:
        reason = "SAM 2 configuration is valid, but the optional torch/sam2 runtime is not installed. No automatic installation was attempted."
    elif not checkpoint.is_file():
        reason = f"SAM 2 checkpoint does not exist: {checkpoint}"
    elif not model_config.is_file():
        reason = f"SAM 2 model config does not exist: {model_config}"
    else:
        reason = "SAM 2 runtime and explicit local model files are present. Adapter execution can be enabled by a later concrete backend binding."

    return SegmentationBackendAvailability(
        backend_id=baseline.backend_id,
        display_name=baseline.display_name,
        installed=baseline.installed,
        configured=True,
        ready=ready,
        optional=True,
        package_versions=baseline.package_versions,
        reason=reason,
    )
