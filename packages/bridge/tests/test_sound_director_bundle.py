import json
import zipfile
from pathlib import Path

from monter_bridge.bundle import create_share_bundle


def test_share_bundle_includes_sound_director_report(tmp_path: Path):
    work = tmp_path / ".monter"
    work.mkdir()
    (work / "project.monter.json").write_text(
        json.dumps({
            "schemaVersion": "monter-project-0.1",
            "projectId": "p",
            "projectName": "Sound Bundle",
            "createdAt": "2026-10-26T00:00:00Z",
            "sourceRootLabel": "RAW",
            "sourceBytes": 0,
            "proxyBytes": 0,
            "assets": [],
        }),
        encoding="utf-8",
    )
    (work / "sound-director.json").write_text(
        json.dumps({
            "schemaVersion": "sound-director-0.1",
            "projectId": "p",
            "boundaries": [],
            "decisions": [],
            "selectedIntents": [],
            "maxJlCuts": 2,
            "notes": [],
        }),
        encoding="utf-8",
    )
    (work / "audio-edit-plan.json").write_text(
        json.dumps({
            "schemaVersion": "audio-edit-plan-0.1",
            "projectId": "p",
            "durationSeconds": 4,
            "events": [],
            "boundaries": [],
            "musicGainDb": -8,
            "notes": [],
        }),
        encoding="utf-8",
    )

    output = tmp_path / "sound.monter.zip"
    result = create_share_bundle(work, output, include_preview=False)
    assert "sound-director.json" in result["includedArtifacts"]
    assert "audio-edit-plan.json" in result["includedArtifacts"]

    with zipfile.ZipFile(output) as archive:
        assert "sound-director.json" in archive.namelist()
        assert "audio-edit-plan.json" in archive.namelist()
