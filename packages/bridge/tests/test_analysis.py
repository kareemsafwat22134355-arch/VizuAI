from pathlib import Path

from monter_bridge.analysis import analyze_project
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
