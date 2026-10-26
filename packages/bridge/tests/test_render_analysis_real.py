from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from monter_bridge.director import default_director_plan
from monter_bridge.render_analysis import analyze_render


FFMPEG_AVAILABLE = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def _make_video(path: Path, source: str, duration: float = 2.4) -> None:
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


@pytest.mark.skipif(not FFMPEG_AVAILABLE, reason="FFmpeg/ffprobe required for real-media render analysis")
def test_render_reanalysis_passes_decodable_normal_output(tmp_path: Path):
    path = tmp_path / "normal.mp4"
    _make_video(path, "testsrc2=size=320x180:rate=12", duration=2.4)

    report = analyze_render(
        path,
        project_id="p",
        expected_duration_seconds=2.4,
        director_plan=default_director_plan(2.4),
        sample_fps=4,
        analysis_width=160,
    )

    assert report.status == "pass"
    assert report.sampled_frames >= 8
    assert report.energy_bins
    assert report.black_frame_fraction < 0.2
    assert abs(report.duration_drift_seconds) <= 0.12
    assert 0 <= report.energy_alignment <= 1


@pytest.mark.skipif(not FFMPEG_AVAILABLE, reason="FFmpeg/ffprobe required for real-media render analysis")
def test_render_reanalysis_fails_duration_drift(tmp_path: Path):
    path = tmp_path / "short.mp4"
    _make_video(path, "testsrc2=size=320x180:rate=12", duration=2.0)

    report = analyze_render(
        path,
        project_id="p",
        expected_duration_seconds=4.0,
        director_plan=default_director_plan(4.0),
        sample_fps=4,
        analysis_width=160,
    )

    assert report.status == "needs_review"
    assert any(finding.code == "duration_drift" and finding.severity == "error" for finding in report.findings)


@pytest.mark.skipif(not FFMPEG_AVAILABLE, reason="FFmpeg/ffprobe required for real-media render analysis")
def test_render_reanalysis_catches_catastrophic_black_output(tmp_path: Path):
    path = tmp_path / "black.mp4"
    _make_video(path, "color=c=black:size=320x180:rate=12", duration=2.0)

    report = analyze_render(
        path,
        project_id="p",
        expected_duration_seconds=2.0,
        director_plan=default_director_plan(2.0),
        sample_fps=4,
        analysis_width=160,
    )

    assert report.status == "needs_review"
    assert report.black_frame_fraction >= 0.98
    assert any(finding.code == "near_black_render" and finding.severity == "error" for finding in report.findings)
