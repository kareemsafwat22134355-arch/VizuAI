from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from monter_bridge.ctl_models import CtlClip, CtlProgram, CtlTransition
from monter_bridge.models import MediaAsset, MonterProject
from monter_bridge.proxy import proxy_path_for
from monter_bridge.render import render_draft


FFMPEG_AVAILABLE = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def _make_clip(path: Path, source: str, duration: float = 3.0) -> None:
    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", source,
            "-t", str(duration),
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            str(path),
        ],
        check=True,
    )


def _duration(path: Path) -> float:
    completed = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "json", str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(json.loads(completed.stdout)["format"]["duration"])


@pytest.mark.skipif(not FFMPEG_AVAILABLE, reason="FFmpeg/ffprobe required for real-media transition test")
def test_directional_bridge_renders_real_media_without_timeline_shrink(tmp_path: Path):
    proxy_dir = tmp_path / "proxies"
    proxy_dir.mkdir()

    assets = [
        MediaAsset(id="a", filename="A.mp4", source_rel_path="A.mp4", source_size_bytes=1, duration_seconds=3, width=320, height=180, fps=12, codec="h264", has_audio=False),
        MediaAsset(id="b", filename="B.mp4", source_rel_path="B.mp4", source_size_bytes=1, duration_seconds=3, width=320, height=180, fps=12, codec="h264", has_audio=False),
    ]
    project = MonterProject(
        project_id="p",
        project_name="Directional Bridge Fixture",
        created_at="2026-10-26T00:00:00Z",
        source_root_label="RAW",
        source_bytes=2,
        proxy_bytes=0,
        assets=assets,
    )

    _make_clip(proxy_path_for(assets[0], proxy_dir), "testsrc2=size=320x180:rate=12")
    _make_clip(proxy_path_for(assets[1], proxy_dir), "testsrc=size=320x180:rate=12")

    ctl = CtlProgram(
        project_id="p",
        duration_seconds=4.0,
        clips=[
            CtlClip(id="s1", asset_id="a", shot_id="sa", source_in_seconds=.5, source_out_seconds=2.5, timeline_in_seconds=0, timeline_out_seconds=2),
            CtlClip(id="s2", asset_id="b", shot_id="sb", source_in_seconds=.5, source_out_seconds=2.5, timeline_in_seconds=2, timeline_out_seconds=4),
        ],
        transitions=[
            CtlTransition(
                boundary_index=1,
                mechanism="directional_bridge",
                duration_seconds=.12,
                parameters={"screenDirection": "right"},
                reason="fixture matched direction",
            )
        ],
        render_fps=12,
        render_width=320,
    )

    output = tmp_path / "directional-bridge.mp4"
    render_draft(ctl, project, proxy_dir, output)

    assert output.exists()
    assert output.stat().st_size > 0
    assert abs(_duration(output) - 4.0) <= 0.10
