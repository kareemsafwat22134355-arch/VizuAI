from pathlib import Path

from monter_bridge.ingest import discover_media, ingest_project
from monter_bridge.models import MediaTechnical


def fake_probe(_: Path) -> MediaTechnical:
    return MediaTechnical(duration_seconds=4.0, width=1920, height=1080, fps=25, codec="h264", has_audio=True)


def test_discover_media_filters_non_video(tmp_path: Path):
    (tmp_path / "A.mp4").write_bytes(b"video")
    (tmp_path / "B.MOV").write_bytes(b"video")
    (tmp_path / "notes.txt").write_text("ignore")
    assert [path.name for path in discover_media(tmp_path)] == ["A.mp4", "B.MOV"]


def test_ingest_builds_portable_manifest(tmp_path: Path):
    media = tmp_path / "camera" / "A001.mp4"
    media.parent.mkdir()
    media.write_bytes(b"123456")

    project = ingest_project(tmp_path, "Trailer", probe=fake_probe)

    assert project.schema_version == "monter-project-0.1"
    assert project.project_name == "Trailer"
    assert project.source_bytes == 6
    assert project.source_root_label == tmp_path.name
    assert len(project.assets) == 1
    asset = project.assets[0]
    assert asset.filename == "A001.mp4"
    assert asset.source_rel_path == "camera/A001.mp4"
    assert asset.source_size_bytes == 6
    assert asset.duration_seconds == 4.0
    assert str(tmp_path.resolve()) not in asset.source_rel_path


def test_portable_serialization_matches_web_contract(tmp_path: Path):
    media = tmp_path / "A001.mp4"
    media.write_bytes(b"123")
    project = ingest_project(tmp_path, "Trailer", probe=fake_probe)

    payload = project.model_dump(by_alias=True)

    assert payload["schemaVersion"] == "monter-project-0.1"
    assert payload["projectName"] == "Trailer"
    assert payload["assets"][0]["sourceRelPath"] == "A001.mp4"
    assert payload["assets"][0]["sourceSizeBytes"] == 3
    assert "source_path" not in payload["assets"][0]
