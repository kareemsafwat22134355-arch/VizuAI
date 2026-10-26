from __future__ import annotations

import math
from pathlib import Path

import cv2
import numpy as np

from .analysis_models import GlobalMotionSample, GlobalMotionSummary, ScreenDirection, TimeRange, ZoomDirection
from .motion import analysis_gray


def decompose_affine(matrix: np.ndarray) -> tuple[float, float, float, float]:
    if matrix.shape != (2, 3):
        raise ValueError("affine matrix must be 2x3")
    a, _, tx = matrix[0]
    c, _, ty = matrix[1]
    scale = math.sqrt(float(a * a + c * c))
    rotation = math.degrees(math.atan2(float(c), float(a)))
    return float(tx), float(ty), rotation, max(scale, 1e-6)


def estimate_pair(previous_gray: np.ndarray, current_gray: np.ndarray) -> tuple[float, float, float, float, float] | None:
    features = cv2.goodFeaturesToTrack(
        previous_gray,
        maxCorners=180,
        qualityLevel=0.01,
        minDistance=6,
        blockSize=7,
    )
    if features is None or len(features) < 8:
        return None

    tracked, status, _ = cv2.calcOpticalFlowPyrLK(
        previous_gray,
        current_gray,
        features,
        None,
        winSize=(21, 21),
        maxLevel=2,
        criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 20, 0.03),
    )
    if tracked is None or status is None:
        return None

    good_old = features[status.ravel() == 1].reshape(-1, 2)
    good_new = tracked[status.ravel() == 1].reshape(-1, 2)
    if len(good_old) < 8:
        return None

    matrix, inliers = cv2.estimateAffinePartial2D(
        good_old,
        good_new,
        method=cv2.RANSAC,
        ransacReprojThreshold=2.5,
        maxIters=1000,
        confidence=0.98,
    )
    if matrix is None:
        return None

    tx, ty, rotation, scale = decompose_affine(matrix)
    inlier_ratio = float(np.mean(inliers)) if inliers is not None and len(inliers) else 0.0
    return tx, ty, rotation, scale, inlier_ratio


def sample_global_motion(
    video_path: Path,
    time_range: TimeRange,
    sample_fps: float = 4.0,
    analysis_width: int = 320,
) -> list[GlobalMotionSample]:
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise ValueError(f"Could not open video: {video_path}")

    source_fps = capture.get(cv2.CAP_PROP_FPS) or 24.0
    frame_step = max(1, round(source_fps / sample_fps))
    start_frame = max(0, round(time_range.start_seconds * source_fps))
    end_frame = max(start_frame, round(time_range.end_seconds * source_fps))
    capture.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    previous_gray: np.ndarray | None = None
    samples: list[GlobalMotionSample] = []
    frame_index = start_frame
    try:
        while frame_index <= end_frame:
            ok, frame = capture.read()
            if not ok:
                break
            if (frame_index - start_frame) % frame_step == 0:
                gray = analysis_gray(frame, analysis_width)
                if previous_gray is not None:
                    estimate = estimate_pair(previous_gray, gray)
                    if estimate is not None:
                        tx, ty, rotation, scale, inlier_ratio = estimate
                        samples.append(GlobalMotionSample(
                            time_seconds=frame_index / source_fps,
                            translation_x=tx,
                            translation_y=ty,
                            rotation_degrees=rotation,
                            scale=scale,
                            inlier_ratio=inlier_ratio,
                        ))
                previous_gray = gray
            frame_index += 1
    finally:
        capture.release()
    return samples


def _screen_direction(tx: float, ty: float, threshold: float = 0.75) -> ScreenDirection:
    magnitude = math.hypot(tx, ty)
    if magnitude < threshold:
        return "static"
    if abs(tx) > abs(ty) * 1.25:
        return "right" if tx > 0 else "left"
    if abs(ty) > abs(tx) * 1.25:
        return "down" if ty > 0 else "up"
    return "mixed"


def _zoom_direction(scale_delta: float, threshold: float = 0.006) -> ZoomDirection:
    if abs(scale_delta) < threshold:
        return "static"
    return "in" if scale_delta > 0 else "out"


def summarize_global_motion(samples: list[GlobalMotionSample]) -> GlobalMotionSummary:
    if not samples:
        return GlobalMotionSummary()

    weights = np.array([max(0.05, sample.inlier_ratio) for sample in samples], dtype=np.float64)
    weights /= weights.sum()
    tx = float(np.sum(np.array([sample.translation_x for sample in samples]) * weights))
    ty = float(np.sum(np.array([sample.translation_y for sample in samples]) * weights))
    rotation = float(np.sum(np.array([sample.rotation_degrees for sample in samples]) * weights))
    scale_delta = float(np.sum(np.array([sample.scale - 1.0 for sample in samples]) * weights))
    confidence = float(np.mean([sample.inlier_ratio for sample in samples]))

    return GlobalMotionSummary(
        dominant_screen_direction=_screen_direction(tx, ty),
        zoom_direction=_zoom_direction(scale_delta),
        mean_translation_x=tx,
        mean_translation_y=ty,
        mean_rotation_degrees=rotation,
        mean_scale_delta=scale_delta,
        confidence=max(0.0, min(1.0, confidence)),
        samples=samples,
    )
