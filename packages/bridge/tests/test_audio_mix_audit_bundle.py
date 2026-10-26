import json
import zipfile
from pathlib import Path

from monter_bridge.bundle import create_share_bundle


def test_bundle_includes_audio_mix_audit(tmp_path: Path):
    work = tmp_path / ".monter"
    work.mkdir()
    (work / "project.monter.json").write_text(
        json.dumps({
            "schemaVersion": "monter-project-0.1",
            "projectId": "p",
            "projectName": "Mix Audit Bundle",
            "createdAt": "2026-10-26T00:00:00Z",
            "sourceRootLabel": "RAW",
            "sourceBytes": 0,
            "proxyBytes": 0,
            "assets": [],
        }),
        encoding="utf-8",
    )
    (work / "audio-mix-audit.json").write_text(
        json.dumps({
            "schemaVersion": "audio-mix-audit-0.1",
            "pathLabel": "rough-cut.audio.mp4",
            "meanVolumeDbfs": -16.0,
            "maxVolumeDbfs": -1.7,
            "clippingSafe": True,
            "safetyThresholdDbfs": -0.5,
            "notes": [],
        }),
        encoding="utf-8",
    )

    output = tmp_path / "mix.monter.zip"
    result = create_share_bundle(work, output, include_preview=False)
    assert "audio-mix-audit.json" in result["includedArtifacts"]
    with zipfile.ZipFile(output) as archive:
        assert "audio-mix-audit.json" in archive.namelist()
