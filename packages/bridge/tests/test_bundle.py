import json
import zipfile
from pathlib import Path

import pytest

from monter_bridge.bundle import create_share_bundle


def test_share_bundle_excludes_proxies_and_raw(tmp_path: Path):
    work_dir = tmp_path / ".monter"
    work_dir.mkdir()
    (work_dir / "project.monter.json").write_text(
        json.dumps(
            {
                "schemaVersion": "monter-project-0.1",
                "projectId": "p1",
                "projectName": "Test",
                "createdAt": "2026-01-01T00:00:00Z",
                "sourceRootLabel": "RAW",
                "sourceBytes": 100,
                "proxyBytes": 10,
                "assets": [
                    {
                        "id": "a1",
                        "filename": "A001.mp4",
                        "sourceRelPath": "camera/A001.mp4",
                        "sourceSizeBytes": 100,
                        "durationSeconds": 2.0,
                        "width": 1920,
                        "height": 1080,
                        "fps": 25.0,
                        "codec": "h264",
                        "hasAudio": False,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (work_dir / "vir.monter.json").write_text("{}", encoding="utf-8")
    (work_dir / "human-corrections.json").write_text(
        json.dumps(
            {
                "schemaVersion": "human-corrections-0.1",
                "projectId": "p1",
                "createdAt": "2026-01-01T00:00:00Z",
                "updatedAt": "2026-01-01T00:01:00Z",
                "corrections": [],
                "notes": [],
            }
        ),
        encoding="utf-8",
    )
    (work_dir / "decision-reviews.json").write_text(
        json.dumps(
            {
                "schemaVersion": "decision-reviews-0.1",
                "projectId": "p1",
                "createdAt": "2026-01-01T00:00:00Z",
                "updatedAt": "2026-01-01T00:02:00Z",
                "reviews": [],
                "notes": [],
            }
        ),
        encoding="utf-8",
    )
    (work_dir / "decision-review-summary.json").write_text(
        json.dumps(
            {
                "schemaVersion": "decision-review-summary-0.1",
                "projectId": "p1",
                "generatedAt": "2026-01-01T00:03:00Z",
                "reviewed": 0,
                "accepted": 0,
                "corrected": 0,
                "acceptanceRate": 0.0,
                "byKind": {},
                "byDirectorRole": {},
                "byTransitionMechanism": {},
                "notes": [],
            }
        ),
        encoding="utf-8",
    )
    (work_dir / "rough-cut.mp4").write_bytes(b"preview")
    proxies = work_dir / "proxies"
    proxies.mkdir()
    (proxies / "a1.mp4").write_bytes(b"proxy-bytes")

    output = tmp_path / "share.monter.zip"
    result = create_share_bundle(work_dir, output)

    assert result["rawMediaIncluded"] is False
    assert result["proxiesIncluded"] is False
    assert output.exists()

    with zipfile.ZipFile(output) as archive:
        names = set(archive.namelist())
        assert "bundle-manifest.json" in names
        assert "project.monter.json" in names
        assert "vir.monter.json" in names
        assert "human-corrections.json" in names
        assert "decision-reviews.json" in names
        assert "decision-review-summary.json" in names
        assert "rough-cut.mp4" in names
        assert all(not name.startswith("proxies/") for name in names)

        manifest = json.loads(archive.read("bundle-manifest.json"))
        assert manifest["rawMediaIncluded"] is False
        assert manifest["proxiesIncluded"] is False
        assert "human-corrections.json" in manifest["includedArtifacts"]
        assert "decision-reviews.json" in manifest["includedArtifacts"]
        assert "decision-review-summary.json" in manifest["includedArtifacts"]


def test_share_bundle_can_exclude_preview(tmp_path: Path):
    work_dir = tmp_path / ".monter"
    work_dir.mkdir()
    (work_dir / "project.monter.json").write_text("{}", encoding="utf-8")
    (work_dir / "rough-cut.mp4").write_bytes(b"preview")

    output = tmp_path / "share.monter.zip"
    create_share_bundle(work_dir, output, include_preview=False)

    with zipfile.ZipFile(output) as archive:
        assert "rough-cut.mp4" not in archive.namelist()


def test_share_bundle_requires_project_manifest(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        create_share_bundle(tmp_path, tmp_path / "share.monter.zip")
