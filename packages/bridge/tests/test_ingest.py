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


def test_ingest_builds_source_linked_manifest(tmp_path: Path):
    media = tmp_path / "camera" / "A001.mp4"
    media.parent.mkdir()
    media.write_bytes(b"123456")

    project = ingest_project(tmp_path, "Trailer", probe=fake_probe)

    assert project.schemaVersion == "monter-project-0.1"
    assert project.projectName == "Trailer"
    assert project.sourceBytes == 6
    assert len(project.assets) == 1
    asset = project.assets[0]
    assert asset.filename == "A001.mp4"
    assert asset.source_size_bytes == 6
    assert asset.duration_seconds == 4.0
    assert asset.source_path.endswith("A001.mp4")
