import numpy as np

from monter_bridge.analysis_models import GlobalMotionSample
from monter_bridge.global_motion import decompose_affine, summarize_global_motion


def test_decompose_affine_extracts_translation_rotation_and_scale():
    angle = np.deg2rad(10)
    scale = 1.05
    matrix = np.array([
        [scale * np.cos(angle), -scale * np.sin(angle), 8.0],
        [scale * np.sin(angle), scale * np.cos(angle), -2.0],
    ], dtype=np.float64)

    tx, ty, rotation, parsed_scale = decompose_affine(matrix)

    assert abs(tx - 8.0) < 1e-6
    assert abs(ty + 2.0) < 1e-6
    assert abs(rotation - 10.0) < 1e-6
    assert abs(parsed_scale - 1.05) < 1e-6


def test_summary_classifies_screen_direction_and_zoom():
    samples = [
        GlobalMotionSample(time_seconds=.25, translation_x=4, translation_y=.2, rotation_degrees=.1, scale=1.02, inlier_ratio=.8),
        GlobalMotionSample(time_seconds=.5, translation_x=5, translation_y=.1, rotation_degrees=.2, scale=1.018, inlier_ratio=.9),
    ]

    summary = summarize_global_motion(samples)

    assert summary.dominant_screen_direction == "right"
    assert summary.zoom_direction == "in"
    assert summary.confidence > .8
