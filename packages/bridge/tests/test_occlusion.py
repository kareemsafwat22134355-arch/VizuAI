import cv2
import numpy as np

from monter_bridge.occlusion import measure_occlusion_cue, summarize_occlusion


def checkerboard(width: int = 160, height: int = 90) -> np.ndarray:
    y, x = np.indices((height, width))
    return (((x // 10 + y // 10) % 2) * 180 + 35).astype(np.uint8)


def test_static_pair_has_negligible_occlusion_likelihood():
    frame = checkerboard()
    sample = measure_occlusion_cue(
        frame,
        frame.copy(),
        time_seconds=1.0,
        global_estimate=(0.0, 0.0, 0.0, 1.0, 1.0),
    )

    assert sample.score < 0.05
    assert sample.residual_change_fraction < 0.01
    assert sample.dominant_edge == "none"
    assert sample.largest_component_bbox_xywh_norm is None
    assert sample.largest_component_centroid_xy_norm is None


def test_compensated_camera_translation_is_not_misread_as_foreground_occlusion():
    previous = checkerboard()
    matrix = np.array([[1.0, 0.0, 7.0], [0.0, 1.0, 0.0]], dtype=np.float32)
    current = cv2.warpAffine(
        previous,
        matrix,
        (previous.shape[1], previous.shape[0]),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REPLICATE,
    )

    sample = measure_occlusion_cue(
        previous,
        current,
        time_seconds=1.1,
        global_estimate=(7.0, 0.0, 0.0, 1.0, 1.0),
    )

    assert sample.score < 0.05
    assert sample.residual_change_fraction < 0.01
    assert sample.largest_component_bbox_xywh_norm is None
    assert sample.largest_component_centroid_xy_norm is None


def test_large_foreground_sweep_touching_edge_scores_as_occlusion_candidate():
    previous = checkerboard()
    current = previous.copy()
    current[:, :44] = 0

    sample = measure_occlusion_cue(
        previous,
        current,
        time_seconds=1.25,
        global_estimate=(0.0, 0.0, 0.0, 1.0, 1.0),
    )

    assert sample.score >= 0.58
    assert sample.largest_component_fraction > 0.15
    assert sample.edge_contact_fraction > 0.45
    assert sample.dominant_edge == "left"
    assert sample.largest_component_bbox_xywh_norm is not None
    assert sample.largest_component_centroid_xy_norm is not None
    x, y, width, height = sample.largest_component_bbox_xywh_norm
    cx, cy = sample.largest_component_centroid_xy_norm
    assert x <= 0.02
    assert 0.20 <= width <= 0.32
    assert y <= 0.05
    assert height >= 0.90
    assert cx < 0.18
    assert 0.35 <= cy <= 0.65


def test_summary_preserves_peak_time_and_edge():
    frame = checkerboard()
    static = measure_occlusion_cue(
        frame,
        frame.copy(),
        time_seconds=1.0,
        global_estimate=(0.0, 0.0, 0.0, 1.0, 1.0),
    )
    swept = frame.copy()
    swept[:, :44] = 0
    occlusion = measure_occlusion_cue(
        frame,
        swept,
        time_seconds=1.25,
        global_estimate=(0.0, 0.0, 0.0, 1.0, 1.0),
    )

    summary = summarize_occlusion([static, occlusion])

    assert summary.peak_score == occlusion.score
    assert summary.peak_time_seconds == 1.25
    assert summary.dominant_edge == "left"
    assert summary.confidence > 0.5
