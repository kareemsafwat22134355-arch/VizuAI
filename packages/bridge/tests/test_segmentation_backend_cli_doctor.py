from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

import monter_bridge.doctor as doctor_module
import monter_bridge.segmentation_backend_cli as backend_cli
from monter_bridge.segmentation_backend_registry import SegmentationBackendAvailability


def _missing_sam2_backends():
    return [
        SegmentationBackendAvailability(
            backend_id="none",
            display_name="Disabled",
            installed=True,
            configured=True,
            ready=True,
            optional=True,
            reason="disabled",
        ),
        SegmentationBackendAvailability(
            backend_id="sam2",
            display_name="Meta SAM 2",
            installed=False,
            configured=False,
            ready=False,
            optional=True,
            reason="missing optional runtime",
        ),
    ]


def test_doctor_does_not_fail_when_optional_sam2_runtime_is_missing(monkeypatch):
    monkeypatch.setattr(doctor_module, "discover_segmentation_backends", _missing_sam2_backends)
    monkeypatch.setattr(
        doctor_module,
        "_binary_status",
        lambda name: {"name": name, "ok": True, "path": f"/usr/bin/{name}", "version": "test"},
    )

    report = doctor_module.doctor_report()

    assert report["ok"] is True
    backends = report["optionalCapabilities"]["segmentationBackends"]
    sam2 = next(item for item in backends if item["backendId"] == "sam2")
    assert sam2["ready"] is False
    assert sam2["optional"] is True


def test_backend_cli_list_is_machine_readable(monkeypatch, capsys):
    monkeypatch.setattr(backend_cli, "discover_segmentation_backends", _missing_sam2_backends)
    monkeypatch.setattr(sys, "argv", ["monter-segmentation-backends", "list"])

    backend_cli.main()
    payload = json.loads(capsys.readouterr().out)

    assert [item["backendId"] for item in payload["backends"]] == ["none", "sam2"]
    assert any("never installs" in note for note in payload["notes"])


def test_backend_cli_validate_none_returns_success(tmp_path: Path, monkeypatch, capsys):
    config = tmp_path / "backend.json"
    config.write_text('{"backendId":"none"}', encoding="utf-8")
    monkeypatch.setattr(sys, "argv", [
        "monter-segmentation-backends",
        "validate",
        "--config",
        str(config),
    ])

    with pytest.raises(SystemExit) as exc:
        backend_cli.main()

    assert exc.value.code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"]["ready"] is True
    assert payload["config"]["allowNetwork"] is False
