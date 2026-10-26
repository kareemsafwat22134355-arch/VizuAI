from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from monter_bridge.microscope import inspect_finished_video


FFMPEG_AVAILABLE = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


@pytest.mark.skipif(not FFMPEG_AVAILABLE, reason="FFmpeg/ffprobe required for real-media microscope smoke test")
def test_microscope_detects_cuts_in_generated_finished_edit(tmp_path: Path):
    output = tmp_path / "finished.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=red:size=320x180:rate=12:duration=1.5",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=320x180:rate=12:duration=1.5",
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:size=320x180:rate=12:duration=1.5",
            "-filter_complex",
            "[0:v][1:v][2:v]concat=n=3:v=1:a=0[v]",
            "-map",
            "[v]",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-pix_fmt",
            "yuv420p",
            str(output),
        ],
        check=True,
    )

    report = inspect_finished_video(output, source_label="Generated Finished Edit")

    assert report.source_label == "Generated Finished Edit"
    assert report.source_duration_seconds >= 4.0
    assert report.shot_count >= 2
    assert report.cut_count == report.shot_count - 1
    assert len(report.motion_energy_arc) == 24
    assert report.mean_shot_duration_seconds > 0
    assert report.limitations
