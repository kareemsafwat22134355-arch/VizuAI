from pathlib import Path

import monter_bridge.analysis as analysis_module
from monter_bridge.analysis import analyze_asset, analyze_project
from monter_bridge.analysis_models import TimeRange
from monter_bridge.models import MediaAsset, MonterProject


def project_with_asset() -> MonterProject:
    return MonterProject(
        project_id="project_test",
        project_name="Test",
        created_at="2026-10-26T00:00:00Z",
        source_root_label="RAW",
        source_bytes=10,
        proxy_bytes=0,
        assets=[
            MediaAsset(
                id="asset_a",
                filename="A.mp4",
                source_rel_path="A.mp4",
                source_size_bytes=10,
                duration_seconds=4,
                width=1920,
                height=1080,
                fps=25,
                codec="h264",
                has_audio=True,
            )
        ],
    )


def test_analyze_project_warns_when_proxy_is_missing(tmp_path: Path):
    vir = analyze_project(project_with_asset(), tmp_path)
    assert vir.schema_version == "vir-0.1"
    assert vir.shots == []
    assert "Proxy missing" in vir.warnings[0]


def test_vir_serializes_with_web_friendly_aliases(tmp_path: Path):
    vir = analyze_project(project_with_asset(), tmp_path)
    payload = vir.model_dump(by_alias=True)
    assert payload["schemaVersion"] == "vir-0.1"
    assert payload["projectId"] == "project_test"


def test_analyze_asset_uses_one_combined_visual_sampler_per_shot(monkeypatch):
    asset = project_with_asset().assets[0]
    ranges = [
        TimeRange(start_seconds=0.0, end_seconds=1.5),
        TimeRange(start_seconds=1.5, end_seconds=4.0),
    ]
    calls: list[TimeRange] = []

    monkeypatch.setattr(analysis_module, "detect_shots", lambda *args, **kwargs: ranges)

    def fake_sample(video_path, time_range, *args, **kwargs):
        calls.append(time_range)
        return [], [], []

    monkeypatch.setattr(analysis_module, "sample_motion_signals", fake_sample)
    shots = analyze_asset(asset, Path("proxy.mp4"))

    assert len(shots) == 2
    assert calls == ranges
    assert all(shot.occlusion.samples == [] for shot in shots)
