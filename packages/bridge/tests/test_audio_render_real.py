from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from monter_bridge.audio_edit import build_audio_edit_plan
from monter_bridge.audio_edit_models import AudioBoundaryIntent
from monter_bridge.ctl_models import CtlClip, CtlProgram, CtlTransition
from monter_bridge.models import MediaAsset, MonterProject
from monter_bridge.proxy import proxy_path_for
from monter_bridge.render import render_draft


FFMPEG_AVAILABLE = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def project() -> MonterProject:
    return MonterProject(
        project_id="p", project_name="Audio Render Fixture", created_at="2026-10-26T00:00:00Z",
        source_root_label="RAW", source_bytes=20, proxy_bytes=10,
        assets=[
            MediaAsset(id="a", filename="a.mp4", source_rel_path="a.mp4", source_size_bytes=10, duration_seconds=4, width=320, height=180, fps=24, codec="h264", has_audio=True),
            MediaAsset(id="b", filename="b.mp4", source_rel_path="b.mp4", source_size_bytes=10, duration_seconds=4, width=320, height=180, fps=24, codec="h264", has_audio=True),
        ],
    )


def ctl() -> CtlProgram:
    return CtlProgram(
        project_id="p", duration_seconds=4,
        clips=[
            CtlClip(id="s1", asset_id="a", shot_id="sa", source_in_seconds=.5, source_out_seconds=2.5, timeline_in_seconds=0, timeline_out_seconds=2),
            CtlClip(id="s2", asset_id="b", shot_id="sb", source_in_seconds=1.0, source_out_seconds=3.0, timeline_in_seconds=2, timeline_out_seconds=4),
        ],
        transitions=[CtlTransition(boundary_index=1, mechanism="hard_cut", reason="fixture")],
        render_fps=24,
        render_width=320,
    )


def _make_av_proxy(path: Path, frequency: int, pattern: str) -> None:
    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", f"{pattern}=size=320x180:rate=24",
            "-f", "lavfi", "-i", f"sine=frequency={frequency}:sample_rate=48000",
            "-t", "4.0",
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k", "-shortest",
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


@pytest.mark.skipif(not FFMPEG_AVAILABLE, reason="FFmpeg/ffprobe required for encoded-media audio render test")
def test_real_j_cut_render_has_audio_and_preserves_picture_duration(tmp_path: Path):
    proxies = tmp_path / "proxies"
    proxies.mkdir()
    manifest = project()
    _make_av_proxy(proxy_path_for(manifest.assets[0], proxies), 440, "testsrc2")
    _make_av_proxy(proxy_path_for(manifest.assets[1], proxies), 880, "testsrc")

    program = ctl()
    plan = build_audio_edit_plan(
        manifest,
        program,
        [AudioBoundaryIntent(boundary_index=1, kind="j_cut", overlap_seconds=.25, reason="incoming 880 Hz tone leads picture")],
    )
    output = tmp_path / "j-cut.mp4"
    render_draft(program, manifest, proxies, output, audio_plan=plan)

    probe = _probe(output)
    stream_types = {stream["codec_type"] for stream in probe["streams"]}
    assert "video" in stream_types
    assert "audio" in stream_types
    assert abs(float(probe["format"]["duration"]) - 4.0) <= .08
    assert output.stat().st_size > 0
