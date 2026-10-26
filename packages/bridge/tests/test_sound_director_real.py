from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from monter_bridge.analysis_models import ShotAnalysis, TimeRange, VirProject
from monter_bridge.ctl_models import CtlClip, CtlProgram, CtlTransition
from monter_bridge.models import MediaAsset, MonterProject
from monter_bridge.proxy import proxy_path_for
from monter_bridge.render import render_draft
from monter_bridge.sound_director import build_sound_directed_audio_plan, direct_sound


FFMPEG_AVAILABLE = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def project() -> MonterProject:
    assets = [
        MediaAsset(id="a", filename="a.mp4", source_rel_path="a.mp4", source_size_bytes=10, duration_seconds=4, width=320, height=180, fps=24, codec="h264", has_audio=True),
        MediaAsset(id="b", filename="b.mp4", source_rel_path="b.mp4", source_size_bytes=10, duration_seconds=4, width=320, height=180, fps=24, codec="h264", has_audio=True),
        MediaAsset(id="c", filename="c.mp4", source_rel_path="c.mp4", source_size_bytes=10, duration_seconds=4, width=320, height=180, fps=24, codec="h264", has_audio=True),
    ]
    return MonterProject(
        project_id="p", project_name="Sound Director Fixture", created_at="2026-10-26T00:00:00Z",
        source_root_label="RAW", source_bytes=30, proxy_bytes=15, assets=assets,
    )


def vir() -> VirProject:
    return VirProject.new("p", [
        ShotAnalysis(id="sa", asset_id="a", range=TimeRange(start_seconds=0, end_seconds=4), mean_motion=0, peak_motion=0, motion_samples=[], edit_anchors=[]),
        ShotAnalysis(id="sb", asset_id="b", range=TimeRange(start_seconds=0, end_seconds=4), mean_motion=0, peak_motion=0, motion_samples=[], edit_anchors=[]),
        ShotAnalysis(id="sc", asset_id="c", range=TimeRange(start_seconds=0, end_seconds=4), mean_motion=0, peak_motion=0, motion_samples=[], edit_anchors=[]),
    ])


def ctl() -> CtlProgram:
    return CtlProgram(
        project_id="p", duration_seconds=6,
        clips=[
            CtlClip(id="s1", asset_id="a", shot_id="sa", source_in_seconds=.5, source_out_seconds=2.5, timeline_in_seconds=0, timeline_out_seconds=2),
            CtlClip(id="s2", asset_id="b", shot_id="sb", source_in_seconds=.5, source_out_seconds=2.5, timeline_in_seconds=2, timeline_out_seconds=4),
            CtlClip(id="s3", asset_id="c", shot_id="sc", source_in_seconds=.5, source_out_seconds=2.5, timeline_in_seconds=4, timeline_out_seconds=6),
        ],
        transitions=[
            CtlTransition(boundary_index=1, mechanism="hard_cut", reason="fixture"),
            CtlTransition(boundary_index=2, mechanism="hard_cut", reason="fixture"),
        ],
        render_fps=24,
        render_width=320,
    )


def _make_proxy(path: Path, active: bool) -> None:
    audio_source = "sine=frequency=660:sample_rate=48000" if active else "anullsrc=r=48000:cl=mono"
    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=24",
            "-f", "lavfi", "-i", audio_source,
            "-t", "4.0", "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k", "-shortest", str(path),
        ],
        check=True,
    )


def _probe(path: Path) -> dict:
    completed = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        check=True, capture_output=True, text=True,
    )
    return json.loads(completed.stdout)


@pytest.mark.skipif(not FFMPEG_AVAILABLE, reason="FFmpeg/ffprobe required for Sound Director encoded-media test")
def test_sound_director_finds_j_then_l_cut_from_real_audio_and_renders_them(tmp_path: Path):
    manifest = project()
    proxies = tmp_path / "proxies"
    proxies.mkdir()
    _make_proxy(proxy_path_for(manifest.assets[0], proxies), active=False)
    _make_proxy(proxy_path_for(manifest.assets[1], proxies), active=True)
    _make_proxy(proxy_path_for(manifest.assets[2], proxies), active=False)

    program = ctl()
    report = direct_sound(manifest, program, vir(), proxies, max_jl_cuts=2)

    decisions = {decision.boundary_index: decision for decision in report.decisions}
    assert decisions[1].recommendation == "j_cut"
    assert decisions[2].recommendation == "l_cut"
    assert [item.recommendation for item in sorted(report.selected_intents, key=lambda item: item.boundary_index)] == ["j_cut", "l_cut"]

    plan = build_sound_directed_audio_plan(manifest, program, report)
    middle = next(event for event in plan.events if event.segment_id == "s2")
    assert middle.timeline_in_seconds < 2.0
    assert middle.timeline_out_seconds > 4.0

    output = tmp_path / "sound-directed.mp4"
    render_draft(program, manifest, proxies, output, audio_plan=plan)
    probe = _probe(output)
    assert {stream["codec_type"] for stream in probe["streams"]} >= {"video", "audio"}
    assert abs(float(probe["format"]["duration"]) - 6.0) <= .08
