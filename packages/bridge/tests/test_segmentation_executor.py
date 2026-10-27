from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from monter_bridge.advanced_analysis_models import (
    AdvancedAnalysisPlan,
    BoundaryAnalysisRequest,
    SourceAnalysisWindow,
)
from monter_bridge.advanced_executor import execute_advanced_analysis
from monter_bridge.models import MediaAsset, MonterProject
from monter_bridge.proxy import proxy_path_for
from monter_bridge.segmentation_models import SegmentationBackendDescriptor

FFMPEG_AVAILABLE = shutil.which("ffmpeg") is not None


class CenterBackend:
    descriptor = SegmentationBackendDescriptor(
        backend_id="fixture-center",
        backend_version="1.0",
        model_id="center-box-v1",
    )

    def __init__(self):
        self.calls = 0

    def segment(self, frame_bgr: np.ndarray, *, time_seconds: float) -> np.ndarray:
        self.calls += 1
        height, width = frame_bgr.shape[:2]
        mask = np.zeros((height, width), dtype=np.uint8)
        mask[height // 4 : 3 * height // 4, width // 4 : 3 * width // 4] = 1
        return mask


def _project() -> MonterProject:
    return MonterProject(
        project_id="p",
        project_name="Segmentation Executor Fixture",
        created_at="2026-10-27T00:00:00Z",
        source_root_label="RAW",
        source_bytes=100,
        proxy_bytes=50,
        assets=[
            MediaAsset(id="a", filename="a.mp4", source_rel_path="a.mp4", source_size_bytes=50, duration_seconds=2, width=320, height=180, fps=24, codec="h264", has_audio=False),
            MediaAsset(id="b", filename="b.mp4", source_rel_path="b.mp4", source_size_bytes=50, duration_seconds=2, width=320, height=180, fps=24, codec="h264", has_audio=False),
        ],
    )


def _plan() -> AdvancedAnalysisPlan:
    return AdvancedAnalysisPlan(
        project_id="p",
        max_boundaries=1,
        requests=[BoundaryAnalysisRequest(
            boundary_index=1,
            priority=.9,
            requested_features=["segmentation"],
            left_window=SourceAnalysisWindow(segment_id="left", asset_id="a", shot_id="sa", source_start_seconds=.2, source_end_seconds=1.4),
            right_window=SourceAnalysisWindow(segment_id="right", asset_id="b", shot_id="sb", source_start_seconds=.2, source_end_seconds=1.4),
            reason="occlusion fixture",
            evidence={"occlusionCandidateScore": .8},
        )],
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


@pytest.mark.skipif(not FFMPEG_AVAILABLE, reason="FFmpeg required for configured segmentation executor test")
def test_executor_runs_configured_segmentation_and_reuses_mask_cache(tmp_path: Path):
    project = _project()
    proxies = tmp_path / "proxies"
    cache = tmp_path / "segmentation-cache"
    proxies.mkdir()
    _make_proxy(proxy_path_for(project.assets[0], proxies), "testsrc2=size=320x180:rate=24")
    _make_proxy(proxy_path_for(project.assets[1], proxies), "testsrc=size=320x180:rate=24")
    backend = CenterBackend()

    first = execute_advanced_analysis(
        project,
        _plan(),
        proxies,
        segmentation_backend=backend,
        segmentation_cache_dir=cache,
        segmentation_sample_fps=4,
        segmentation_analysis_width=160,
    )

    boundary = first.boundaries[0]
    feature = next(item for item in boundary.features if item.feature == "segmentation")
    assert feature.status == "completed"
    assert feature.backend == "fixture-center"
    assert boundary.left_segmentation is not None
    assert boundary.right_segmentation is not None
    assert boundary.left_segmentation.cache_hit is False
    assert boundary.right_segmentation.cache_hit is False
    assert feature.metrics["modelId"] == "center-box-v1"
    assert feature.metrics["leftMeanForegroundFraction"] == pytest.approx(.25, abs=.02)
    calls_after_first = backend.calls
    assert calls_after_first > 0

    second = execute_advanced_analysis(
        project,
        _plan(),
        proxies,
        segmentation_backend=backend,
        segmentation_cache_dir=cache,
        segmentation_sample_fps=4,
        segmentation_analysis_width=160,
    )

    boundary2 = second.boundaries[0]
    feature2 = next(item for item in boundary2.features if item.feature == "segmentation")
    assert feature2.status == "completed"
    assert boundary2.left_segmentation is not None and boundary2.left_segmentation.cache_hit is True
    assert boundary2.right_segmentation is not None and boundary2.right_segmentation.cache_hit is True
    assert feature2.metrics["leftCacheHit"] is True
    assert feature2.metrics["rightCacheHit"] is True
    assert backend.calls == calls_after_first
