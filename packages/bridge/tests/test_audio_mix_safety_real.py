from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from monter_bridge.audio_edit import build_audio_edit_plan
from monter_bridge.audio_mix_audit import audit_audio_mix
from monter_bridge.ctl_models import CtlClip, CtlProgram
from monter_bridge.models import MediaAsset, MonterProject
from monter_bridge.proxy import proxy_path_for
from monter_bridge.render import render_command, render_draft


FFMPEG_AVAILABLE = shutil.which("ffmpeg") is not None


def project() -> MonterProject:
    return MonterProject(
        project_id="p", project_name="Hot Mix Fixture", created_at="2026-10-26T00:00:00Z",
        source_root_label="RAW", source_bytes=10, proxy_bytes=5,
        assets=[
            MediaAsset(
                id="a", filename="a.mp4", source_rel_path="a.mp4", source_size_bytes=10,
                duration_seconds=4, width=320, height=180, fps=24, codec="h264", has_audio=True,
            )
        ],
    )


def ctl() -> CtlProgram:
    return CtlProgram(
        project_id="p", duration_seconds=3,
        clips=[
            CtlClip(
                id="s1", asset_id="a", shot_id="sa",
                source_in_seconds=.5, source_out_seconds=3.5,
                timeline_in_seconds=0, timeline_out_seconds=3,
            )
        ],
        transitions=[], render_fps=24, render_width=320,
    )


def _make_hot_av(path: Path) -> None:
    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=24",
            "-f", "lavfi", "-i", "aevalsrc=0.9*sin(2*PI*440*t):s=48000",
            "-t", "4.0", "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "160k", "-shortest", str(path),
        ],
        check=True,
    )


def _make_hot_music(path: Path) -> None:
    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "aevalsrc=0.9*sin(2*PI*440*t):s=48000",
            "-t", "4.0", "-c:a", "pcm_s16le", str(path),
        ],
        check=True,
    )


@pytest.mark.skipif(not FFMPEG_AVAILABLE, reason="FFmpeg required for rendered mix safety test")
def test_hot_source_plus_music_mix_is_limited_and_safe_after_aac(tmp_path: Path):
    manifest = project()
    program = ctl()
    proxies = tmp_path / "proxies"
    proxies.mkdir()
    proxy = proxy_path_for(manifest.assets[0], proxies)
    music = tmp_path / "music.wav"
    _make_hot_av(proxy)
    _make_hot_music(music)

    plan = build_audio_edit_plan(
        manifest,
        program,
        source_gain_db=12.0,
        music_gain_db=12.0,
    )
    output = tmp_path / "hot-mix.mp4"
    command_text = " ".join(render_command(program, manifest, proxies, output, music=music, audio_plan=plan))
    assert "amix=inputs=2:duration=longest:dropout_transition=0:normalize=0" in command_text
    assert "alimiter=limit=0.800000:attack=5:release=50:level=0:latency=1" in command_text

    render_draft(program, manifest, proxies, output, music=music, audio_plan=plan)
    audit = audit_audio_mix(output)

    assert audit.clipping_safe is True
    assert audit.max_volume_dbfs <= audit.safety_threshold_dbfs
    assert audit.max_volume_dbfs < 0
    assert output.stat().st_size > 0
