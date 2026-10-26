import cv2
import numpy as np

from monter_bridge.analysis_models import MotionSample, TimeRange
from monter_bridge.motion import analysis_gray, build_motion_anchors, flow_magnitude


def frame_with_square(x: int) -> np.ndarray:
    frame = np.zeros((120, 160, 3), dtype=np.uint8)
    cv2.rectangle(frame, (x, 40), (x + 35, 75), (255, 255, 255), -1)
    return frame


def test_flow_magnitude_detects_translation():
    still = analysis_gray(frame_with_square(20))
    moved = analysis_gray(frame_with_square(38))
    assert flow_magnitude(still, moved) > 0


def test_motion_anchors_include_gesture_phases():
    samples = [
        MotionSample(time_seconds=0.25, magnitude=0.1),
        MotionSample(time_seconds=0.50, magnitude=1.4),
        MotionSample(time_seconds=0.75, magnitude=4.0),
        MotionSample(time_seconds=1.00, magnitude=1.1),
        MotionSample(time_seconds=1.25, magnitude=0.1),
    ]
    anchors = build_motion_anchors(samples, TimeRange(start_seconds=0, end_seconds=1.5))
    types = {anchor.type for anchor in anchors}
    assert {"clip_start", "clip_end", "motion_onset", "motion_peak", "motion_settle"}.issubset(types)
    peak = next(anchor for anchor in anchors if anchor.type == "motion_peak")
    assert peak.time_seconds == 0.75
