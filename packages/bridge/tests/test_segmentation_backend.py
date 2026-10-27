from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import cv2
import numpy as np
import pytest

from monter_bridge.advanced_analysis_models import SourceAnalysisWindow
from monter_bridge.segmentation import execute_segmentation_window
from monter_bridge.segmentation_models import SegmentationBackendDescriptor

FFMPEG_AVAILABLE = shutil.which("ffmpeg") is not None


class LeftHalfBackend:
    def __init__(self, threshold: float = .5):
        self.calls = 0
        self.descriptor = SegmentationBackendDescriptor(
            backend_id="test-threshold",
            backend_version="1.0",
            model_id="left-half-v1",
            parameters={"threshold": threshold},
        )

    def segment(self, frame_bgr: np.ndarray, *, time_seconds: float) -> np.ndarray:
        self.calls += 1
        mask = np.zeros(frame_bgr.shape[:2], dtype=np.uint8)
        mask[:, : frame_bgr.shape[1] // 2] = 1
        return mask


class BadShapeBackend:
    descriptor = SegmentationBackendDescriptor(
        backend_id="bad-shape",
        backend_version="1.0",
        model_id="bad-v1",
    )

    def segment(self, frame_bgr: np.ndarray, *, time_seconds: float) -> np.ndarray:
        return np.ones((4, 4), dtype=np.uint8)


def _make_video(path: Path) -> None:
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


def _window() -> SourceAnalysisWindow:
    return SourceAnalysisWindow(
        segment_id="s1",
        asset_id="a",
        shot_id="sa",
        source_start_seconds=.25,
        source_end_seconds=1.25,
    )


@pytest.mark.skipif(not FFMPEG_AVAILABLE, reason="FFmpeg required for encoded segmentation cache test")
def test_segmentation_backend_writes_masks_then_hits_cache_without_reexecution(tmp_path: Path):
    video = tmp_path / "proxy.mp4"
    cache = tmp_path / "segmentation-cache"
    _make_video(video)
    backend = LeftHalfBackend()

    first = execute_segmentation_window(
        video, _window(), "left", cache, backend,
        sample_fps=4.0, analysis_width=160,
    )

    assert first.cache_hit is False
    assert first.input_digest
    assert len(first.input_digest) == 32
    assert len(first.frames) >= 3
    first_call_count = backend.calls
    assert first_call_count == len(first.frames)
    assert first.backend.backend_id == "test-threshold"
    assert first.backend.parameters["threshold"] == .5
    assert first.analysis_width == 160
    for frame in first.frames:
        assert frame.width == 160
        assert frame.foreground_fraction == pytest.approx(.5, abs=.01)
        assert frame.bbox_xywh_norm is not None
        assert frame.bbox_xywh_norm[0] == pytest.approx(0)
        assert frame.bbox_xywh_norm[2] == pytest.approx(.5, abs=.01)
        mask_path = cache / frame.mask_path
        assert mask_path.is_file()
        mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
        assert mask is not None
        assert set(np.unique(mask)).issubset({0, 255})

    second = execute_segmentation_window(
        video, _window(), "left", cache, backend,
        sample_fps=4.0, analysis_width=160,
    )

    assert second.cache_hit is True
    assert second.cache_key == first.cache_key
    assert second.input_digest == first.input_digest
    assert backend.calls == first_call_count
    assert [frame.mask_path for frame in second.frames] == [frame.mask_path for frame in first.frames]


@pytest.mark.skipif(not FFMPEG_AVAILABLE, reason="FFmpeg required for encoded segmentation cache test")
def test_segmentation_cache_key_changes_with_sampling_or_backend_parameters(tmp_path: Path):
    video = tmp_path / "proxy.mp4"
    cache = tmp_path / "segmentation-cache"
    _make_video(video)

    base_backend = LeftHalfBackend(threshold=.5)
    changed_backend = LeftHalfBackend(threshold=.7)
    narrow = execute_segmentation_window(video, _window(), "left", cache, base_backend, sample_fps=4, analysis_width=160)
    wide = execute_segmentation_window(video, _window(), "left", cache, base_backend, sample_fps=4, analysis_width=240)
    changed_params = execute_segmentation_window(video, _window(), "left", cache, changed_backend, sample_fps=4, analysis_width=160)

    assert narrow.cache_key != wide.cache_key
    assert narrow.cache_key != changed_params.cache_key
    assert narrow.input_digest == wide.input_digest == changed_params.input_digest
    assert narrow.frames[0].width == 160
    assert wide.frames[0].width == 240


@pytest.mark.skipif(not FFMPEG_AVAILABLE, reason="FFmpeg required for encoded segmentation validation test")
def test_invalid_backend_mask_shape_fails_without_leaving_completed_cache(tmp_path: Path):
    video = tmp_path / "proxy.mp4"
    cache = tmp_path / "segmentation-cache"
    _make_video(video)

    with pytest.raises(ValueError, match="does not match frame shape"):
        execute_segmentation_window(video, _window(), "left", cache, BadShapeBackend(), sample_fps=4, analysis_width=160)

    assert not list(cache.glob("seg_*/manifest.json"))
