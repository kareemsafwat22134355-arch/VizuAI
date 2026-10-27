from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

import monter_bridge.segmentation_backend_registry as registry
from monter_bridge.segmentation_backend_config import SegmentationBackendConfig
from monter_bridge.segmentation_backend_registry import validate_segmentation_backend_config


def test_none_backend_is_valid_and_requires_no_runtime():
    config = SegmentationBackendConfig()
    status = validate_segmentation_backend_config(config)

    assert config.backend_id == "none"
    assert config.allow_network is False
    assert status.ready is True
    assert status.optional is True


def test_config_rejects_network_backed_model_loading():
    with pytest.raises(ValidationError, match="Network-backed model loading is intentionally disabled"):
        SegmentationBackendConfig(
            backend_id="sam2",
            checkpoint_path="weights.pt",
            model_config_path="sam2.yaml",
            allow_network=True,
        )


def test_sam2_requires_explicit_local_checkpoint_and_model_config():
    with pytest.raises(ValidationError, match="checkpointPath and modelConfigPath"):
        SegmentationBackendConfig(backend_id="sam2")


def test_none_backend_cannot_smuggle_model_configuration():
    with pytest.raises(ValidationError, match="backendId=none"):
        SegmentationBackendConfig(backend_id="none", model_id="unexpected")


def test_sam2_ready_only_when_runtime_and_local_files_exist(monkeypatch, tmp_path: Path):
    checkpoint = tmp_path / "model.pt"
    model_config = tmp_path / "model.yaml"
    checkpoint.write_bytes(b"weights")
    model_config.write_text("model: test", encoding="utf-8")

    monkeypatch.setattr(registry, "_module_available", lambda name: name in {"torch", "sam2"})
    monkeypatch.setattr(registry, "_package_version", lambda name: {"torch": "2.x", "sam2": "local"}.get(name))

    config = SegmentationBackendConfig(
        backend_id="sam2",
        checkpoint_path=str(checkpoint),
        model_config_path=str(model_config),
        parameters={"offloadVideoToCpu": True},
    )
    status = validate_segmentation_backend_config(config)

    assert status.installed is True
    assert status.configured is True
    assert status.ready is True
    assert status.package_versions["torch"] == "2.x"
    assert status.package_versions["sam2"] == "local"


def test_sam2_missing_runtime_stays_optional_and_not_ready(monkeypatch, tmp_path: Path):
    checkpoint = tmp_path / "model.pt"
    model_config = tmp_path / "model.yaml"
    checkpoint.write_bytes(b"weights")
    model_config.write_text("model: test", encoding="utf-8")

    monkeypatch.setattr(registry, "_module_available", lambda name: False)
    monkeypatch.setattr(registry, "_package_version", lambda name: None)

    config = SegmentationBackendConfig(
        backend_id="sam2",
        checkpoint_path=str(checkpoint),
        model_config_path=str(model_config),
    )
    status = validate_segmentation_backend_config(config)

    assert status.installed is False
    assert status.configured is True
    assert status.ready is False
    assert status.optional is True
    assert "No automatic installation" in status.reason
