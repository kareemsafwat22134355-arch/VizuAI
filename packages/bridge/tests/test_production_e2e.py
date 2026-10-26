from __future__ import annotations

import json
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

from monter_bridge.bundle import create_share_bundle
from monter_bridge.production import produce_project


FFMPEG_AVAILABLE = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def _make_clip(path: Path, lavfi_source: str, duration: float = 2.4) -> None:
    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", lavfi_source,
            "-t", str(duration),
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            str(path),
        ],
        check=True,
    )


def _make_av_clip(path: Path, color: str, frequency: int, duration: float = 2.4) -> None:
    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", f"color=c={color}:size=320x180:rate=12",
            "-f", "lavfi", "-i", f"sine=frequency={frequency}:sample_rate=48000",
            "-t", str(duration), "-shortest",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "96k",
            str(path),
        ],
        check=True,
    )


def _probe(path: Path) -> dict:
    completed = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


@pytest.mark.skipif(not FFMPEG_AVAILABLE, reason="FFmpeg/ffprobe required for real-media smoke test")
def test_produce_real_media_end_to_end(tmp_path: Path):
    raw = tmp_path / "RAW"
    raw.mkdir()
    _make_clip(raw / "01_static.mp4", "color=c=0x20242a:size=320x180:rate=12")
    _make_clip(raw / "02_motion.mp4", "testsrc2=size=320x180:rate=12")
    _make_clip(raw / "03_pattern.mp4", "testsrc=size=320x180:rate=12")

    work = tmp_path / ".monter"
    report = produce_project(
        source_root=raw,
        project_name="E2E Fixture",
        work_dir=work,
        duration=4.0,
        width=320,
        fps=12,
        max_revision_iterations=1,
        render=True,
    )

    assert report.assets_ingested == 3
    assert report.shots_analyzed >= 3
    assert report.edit_segments >= 4
    assert report.advanced_pass_executed is True
    assert report.sound_pass_executed is True
    assert report.audio_mix_audited is False
    assert report.audio_mix_safe is None
    assert report.render_reanalysis_executed is True
    assert report.render_integrity_safe is True
    assert report.render_energy_alignment is not None

    expected = {
        "project.monter.json", "vir.monter.json", "director-plan.json", "edit-plan.json",
        "ctl.json", "critic-report.json", "transition-opportunities.json",
        "advanced-analysis-plan.json", "advanced-analysis-results.json", "transition-refinement.json",
        "sound-director.json", "audio-edit-plan.json", "render-analysis.json",
        "production-report.json", "edit.otio", "rough-cut.mp4",
    }
    assert expected.issubset({path.name for path in work.iterdir() if path.is_file()})
    assert (work / "rough-cut.mp4").stat().st_size > 0

    opportunities = json.loads((work / "transition-opportunities.json").read_text(encoding="utf-8"))
    assert opportunities["projectId"] == report.project_id
    assert len(opportunities["boundaries"]) == max(0, report.edit_segments - 1)
    assert all(
        any(candidate["mechanism"] == "hard_cut" for candidate in boundary["candidates"])
        for boundary in opportunities["boundaries"]
    )

    advanced = json.loads((work / "advanced-analysis-plan.json").read_text(encoding="utf-8"))
    assert advanced["schemaVersion"] == "advanced-analysis-plan-0.1"
    assert advanced["projectId"] == report.project_id
    assert advanced["maxBoundaries"] == 4
    valid_features = {"dense_flow", "depth", "segmentation"}
    assert all(request["boundaryIndex"] >= 1 for request in advanced["requests"])
    assert all(set(request["requestedFeatures"]).issubset(valid_features) for request in advanced["requests"])

    advanced_results = json.loads((work / "advanced-analysis-results.json").read_text(encoding="utf-8"))
    refinement = json.loads((work / "transition-refinement.json").read_text(encoding="utf-8"))
    sound = json.loads((work / "sound-director.json").read_text(encoding="utf-8"))
    render_analysis = json.loads((work / "render-analysis.json").read_text(encoding="utf-8"))
    assert advanced_results["projectId"] == report.project_id
    assert refinement["projectId"] == report.project_id
    assert sound["projectId"] == report.project_id
    assert render_analysis["schemaVersion"] == "render-analysis-0.1"
    assert render_analysis["projectId"] == report.project_id
    assert render_analysis["status"] == "pass"
    assert render_analysis["sampledFrames"] > 0

    manifest = json.loads((work / "project.monter.json").read_text(encoding="utf-8"))
    assert len(manifest["assets"]) == 3
    for asset in manifest["assets"]:
        assert not Path(asset["sourceRelPath"]).is_absolute()
        assert str(raw) not in asset["sourceRelPath"]
        proxy = work / "proxies" / f"{asset['id']}.mp4"
        proxy_meta = proxy.with_suffix(proxy.suffix + ".meta.json")
        assert proxy.exists()
        assert proxy_meta.exists()

    bundle = tmp_path / "share.monter.zip"
    bundle_result = create_share_bundle(work, bundle, include_preview=True)
    assert bundle_result["rawMediaIncluded"] is False
    assert bundle_result["proxiesIncluded"] is False

    with zipfile.ZipFile(bundle) as archive:
        names = archive.namelist()
        assert "project.monter.json" in names
        assert "transition-opportunities.json" in names
        assert "advanced-analysis-plan.json" in names
        assert "advanced-analysis-results.json" in names
        assert "transition-refinement.json" in names
        assert "sound-director.json" in names
        assert "audio-edit-plan.json" in names
        assert "render-analysis.json" in names
        assert "rough-cut.mp4" in names
        assert all(not name.startswith("proxies/") for name in names)


@pytest.mark.skipif(not FFMPEG_AVAILABLE, reason="FFmpeg/ffprobe required for real-media smoke test")
def test_produce_audio_media_runs_sound_render_mix_audit_and_reanalysis(tmp_path: Path):
    raw = tmp_path / "RAW"
    raw.mkdir()
    _make_av_clip(raw / "01_blue.mp4", "0x203060", 330)
    _make_av_clip(raw / "02_red.mp4", "0x602020", 440)
    _make_av_clip(raw / "03_green.mp4", "0x206030", 550)

    work = tmp_path / ".monter"
    report = produce_project(
        source_root=raw,
        project_name="Audio E2E Fixture",
        work_dir=work,
        duration=4.0,
        width=320,
        fps=12,
        max_revision_iterations=0,
        render=True,
    )

    assert report.sound_pass_executed is True
    assert report.audio_mix_audited is True
    assert report.audio_mix_safe is True
    assert report.render_reanalysis_executed is True
    assert report.render_integrity_safe is True
    assert "sound-director.json" in report.artifacts
    assert "audio-edit-plan.json" in report.artifacts
    assert "audio-mix-audit.json" in report.artifacts
    assert "render-analysis.json" in report.artifacts

    audio_plan = json.loads((work / "audio-edit-plan.json").read_text(encoding="utf-8"))
    audit = json.loads((work / "audio-mix-audit.json").read_text(encoding="utf-8"))
    render_analysis = json.loads((work / "render-analysis.json").read_text(encoding="utf-8"))
    assert audio_plan["projectId"] == report.project_id
    assert len(audio_plan["events"]) > 0
    assert audit["clippingSafe"] is True
    assert audit["maxVolumeDbfs"] <= audit["safetyThresholdDbfs"]
    assert render_analysis["status"] == "pass"
    assert render_analysis["hasAudio"] is True

    probe = _probe(work / "rough-cut.mp4")
    codec_types = {stream["codec_type"] for stream in probe["streams"]}
    assert "video" in codec_types
    assert "audio" in codec_types
    assert float(probe["format"]["duration"]) == pytest.approx(4.0, abs=0.08)
