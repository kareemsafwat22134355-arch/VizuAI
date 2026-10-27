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
from monter_bridge.segmentation_prompt_models import SegmentationPromptContext

FFMPEG_AVAILABLE = shutil.which("ffmpeg") is not None


class PromptWindowBackend:
    descriptor = SegmentationBackendDescriptor(
        backend_id="fixture-prompt-window",
        backend_version="1.0",
        model_id="prompt-window-v1",
    )

    def __init__(self):
        self.calls = 0
        self.prompts: list[SegmentationPromptContext] = []

    def segment_window(
        self,
        frames_bgr: list[np.ndarray],
        *,
        times_seconds: list[float],
        prompt: SegmentationPromptContext,
    ) -> list[np.ndarray]:
        self.calls += 1
        self.prompts.append(prompt)
        masks: list[np.ndarray] = []
        x1, y1, x2, y2 = prompt.box_xyxy_norm
        for frame in frames_bgr:
            height, width = frame.shape[:2]
            mask = np.zeros((height, width), dtype=np.uint8)
            px1 = max(0, min(width - 1, round(x1 * width)))
            py1 = max(0, min(height - 1, round(y1 * height)))
            px2 = max(px1 + 1, min(width, round(x2 * width)))
            py2 = max(py1 + 1, min(height, round(y2 * height)))
            mask[py1:py2, px1:px2] = 1
            masks.append(mask)
        return masks


def _project() -> MonterProject:
    return MonterProject(
        project_id="p",
        project_name="Prompted Segmentation Executor Fixture",
        created_at="2026-10-27T00:00:00Z",
        source_root_label="RAW",
        source_bytes=100,
        proxy_bytes=50,
        assets=[
            MediaAsset(
                id="a", filename="a.mp4", source_rel_path="a.mp4",
                source_size_bytes=50, duration_seconds=2,
                width=320, height=180, fps=24, codec="h264", has_audio=False,
            ),
            MediaAsset(
                id="b", filename="b.mp4", source_rel_path="b.mp4",
                source_size_bytes=50, duration_seconds=2,
                width=320, height=180, fps=24, codec="h264", has_audio=False,
            ),
        ],
    )


def _prompt() -> SegmentationPromptContext:
    return SegmentationPromptContext(
        side="left",
        source_time_seconds=.9,
        point_xy_norm=[.15, .5],
        box_xyxy_norm=[.02, .18, .34, .82],
        confidence=.84,
        occlusion_score=.84,
        dominant_edge="left",
    )


def _plan() -> AdvancedAnalysisPlan:
    return AdvancedAnalysisPlan(
        project_id="p",
        max_boundaries=1,
        requests=[BoundaryAnalysisRequest(
            boundary_index=1,
            priority=.92,
            requested_features=["segmentation"],
            left_window=SourceAnalysisWindow(
                segment_id="left", asset_id="a", shot_id="sa",
                source_start_seconds=.4, source_end_seconds=1.3,
            ),
            right_window=SourceAnalysisWindow(
                segment_id="right", asset_id="b", shot_id="sb",
                source_start_seconds=.4, source_end_seconds=1.3,
            ),
            left_segmentation_prompt=_prompt(),
            right_segmentation_prompt=None,
            reason="Only outgoing physical occlusion evidence has validated prompt geometry.",
            evidence={
                "occlusionCandidateScore": .84,
                "occlusionSide": "outgoing",
                "leftSegmentationPrompt": True,
                "rightSegmentationPrompt": False,
            },
        )],
    )


def _make_proxy(path: Path) -> None:
    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=24",
            "-t", "2.0",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            str(path),
        ],
        check=True,
    )


@pytest.mark.skipif(not FFMPEG_AVAILABLE, reason="FFmpeg required for prompted segmentation executor test")
def test_executor_runs_only_prompted_side_and_never_requires_unmotivated_proxy(tmp_path: Path):
    project = _project()
    proxies = tmp_path / "proxies"
    cache = tmp_path / "segmentation-cache"
    proxies.mkdir()

    # Deliberately create ONLY the left proxy. Any accidental right-side execution must fail.
    _make_proxy(proxy_path_for(project.assets[0], proxies))
    right_proxy = proxy_path_for(project.assets[1], proxies)
    assert not right_proxy.exists()

    backend = PromptWindowBackend()
    result = execute_advanced_analysis(
        project,
        _plan(),
        proxies,
        segmentation_backend=backend,
        segmentation_cache_dir=cache,
        segmentation_sample_fps=4,
        segmentation_analysis_width=160,
    )

    boundary = result.boundaries[0]
    feature = next(item for item in boundary.features if item.feature == "segmentation")
    assert feature.status == "completed"
    assert feature.backend == "fixture-prompt-window"
    assert backend.calls == 1
    assert backend.prompts == [_prompt()]
    assert boundary.left_segmentation is not None
    assert boundary.left_segmentation.execution_mode == "window"
    assert boundary.left_segmentation.prompt_context == _prompt()
    assert boundary.right_segmentation is None
    assert feature.metrics["executedSides"] == "left"
    assert feature.metrics["leftExecuted"] is True
    assert feature.metrics["rightExecuted"] is False
    assert feature.metrics["leftPrompted"] is True
    assert feature.metrics["rightPrompted"] is False
    assert feature.metrics["rightSampleCount"] == 0
