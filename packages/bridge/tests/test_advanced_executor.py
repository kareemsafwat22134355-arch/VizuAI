from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from monter_bridge.advanced_analysis_models import (
    AdvancedAnalysisPlan,
    BoundaryAnalysisRequest,
    SourceAnalysisWindow,
)
from monter_bridge.advanced_executor import execute_advanced_analysis
from monter_bridge.models import MediaAsset, MonterProject
from monter_bridge.proxy import proxy_path_for


FFMPEG_AVAILABLE = shutil.which("ffmpeg") is not None


def project() -> MonterProject:
    return MonterProject(
        project_id="p",
        project_name="Advanced Executor Fixture",
        created_at="2026-10-26T00:00:00Z",
        source_root_label="RAW",
        source_bytes=100,
        proxy_bytes=50,
        assets=[
            MediaAsset(id="a", filename="a.mp4", source_rel_path="a.mp4", source_size_bytes=50, duration_seconds=2.0, width=320, height=180, fps=24.0, codec="h264", has_audio=False),
            MediaAsset(id="b", filename="b.mp4", source_rel_path="b.mp4", source_size_bytes=50, duration_seconds=2.0, width=320, height=180, fps=24.0, codec="h264", has_audio=False),
        ],
    )


def plan(project_id: str = "p") -> AdvancedAnalysisPlan:
    return AdvancedAnalysisPlan(
        project_id=project_id,
        max_boundaries=2,
        requests=[
            BoundaryAnalysisRequest(
                boundary_index=1,
                priority=.9,
                requested_features=["dense_flow", "depth"],
                left_window=SourceAnalysisWindow(segment_id="s1", asset_id="a", shot_id="sa", source_start_seconds=.2, source_end_seconds=1.6),
                right_window=SourceAnalysisWindow(segment_id="s2", asset_id="b", shot_id="sb", source_start_seconds=.2, source_end_seconds=1.6),
                reason="fixture",
                evidence={
                    "recommendedMechanism": "zoom_bridge",
                    "leftSourceOutSeconds": 1.20,
                    "rightSourceInSeconds": .60,
                },
            )
        ],
    )


def _make_proxy(path: Path, source: str) -> None:
    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", source,
            "-t", "2.0",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            str(path),
        ],
        check=True,
    )


@pytest.mark.skipif(not FFMPEG_AVAILABLE, reason="FFmpeg required for encoded-media dense-flow test")
def test_executor_runs_dense_flow_and_reports_unavailable_depth(tmp_path: Path):
    proxies = tmp_path / "proxies"
    proxies.mkdir()
    manifest = project()
    _make_proxy(proxy_path_for(manifest.assets[0], proxies), "testsrc2=size=320x180:rate=24")
    _make_proxy(proxy_path_for(manifest.assets[1], proxies), "testsrc=size=320x180:rate=24")

    results = execute_advanced_analysis(manifest, plan(), proxies, sample_fps=12, analysis_width=160)

    assert results.project_id == "p"
    assert len(results.boundaries) == 1
    boundary = results.boundaries[0]
    dense_flow = next(feature for feature in boundary.features if feature.feature == "dense_flow")
    depth = next(feature for feature in boundary.features if feature.feature == "depth")

    assert dense_flow.status == "completed"
    assert dense_flow.backend == "opencv-farneback"
    assert boundary.request_evidence["leftSourceOutSeconds"] == pytest.approx(1.20)
    assert boundary.request_evidence["rightSourceInSeconds"] == pytest.approx(.60)
    assert boundary.left_flow is not None and boundary.left_flow.sample_count > 0
    assert boundary.right_flow is not None and boundary.right_flow.sample_count > 0
    assert boundary.flow_direction_compatibility is not None
    assert 0 <= boundary.flow_direction_compatibility <= 1

    for summary in (boundary.left_flow, boundary.right_flow):
        assert summary.peak_time_seconds is not None
        assert summary.onset_time_seconds is not None
        assert summary.source_start_seconds <= summary.onset_time_seconds <= summary.peak_time_seconds <= summary.source_end_seconds
        assert summary.peak_magnitude >= 0
        assert summary.temporal_contrast >= 0

    assert "leftPeakTimeSeconds" in dense_flow.metrics
    assert "leftOnsetTimeSeconds" in dense_flow.metrics
    assert "rightPeakTimeSeconds" in dense_flow.metrics
    assert "rightOnsetTimeSeconds" in dense_flow.metrics
    assert depth.status == "backend_unavailable"
    assert depth.backend == "unconfigured"


def test_executor_rejects_cross_project_plan(tmp_path: Path):
    with pytest.raises(ValueError, match="projectId"):
        execute_advanced_analysis(project(), plan("other"), tmp_path)
