from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from .analysis_models import EditAnchor, MotionSample, TimeRange


def analysis_gray(frame: np.ndarray, width: int = 320) -> np.ndarray:
    height, source_width = frame.shape[:2]
    if source_width > width:
        target_height = max(1, round(height * width / source_width))
        frame = cv2.resize(frame, (width, target_height), interpolation=cv2.INTER_AREA)
    return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)


def flow_magnitude(previous_gray: np.ndarray, current_gray: np.ndarray) -> float:
    flow = cv2.calcOpticalFlowFarneback(
        previous_gray,
        current_gray,
        None,
        pyr_scale=0.5,
        levels=2,
        winsize=15,
        iterations=2,
        poly_n=5,
        poly_sigma=1.1,
        flags=0,
    )
    magnitude, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
    return float(np.percentile(magnitude, 75))


def sample_motion(
    video_path: Path,
    time_range: TimeRange,
    sample_fps: float = 4.0,
    analysis_width: int = 320,
) -> list[MotionSample]:
    if sample_fps <= 0:
        raise ValueError("sample_fps must be > 0")

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise ValueError(f"Could not open video: {video_path}")

    source_fps = capture.get(cv2.CAP_PROP_FPS) or 24.0
    frame_step = max(1, round(source_fps / sample_fps))
    start_frame = max(0, round(time_range.start_seconds * source_fps))
    end_frame = max(start_frame, round(time_range.end_seconds * source_fps))
    capture.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    samples: list[MotionSample] = []
    previous_gray: np.ndarray | None = None
    frame_index = start_frame

    try:
        while frame_index <= end_frame:
            ok, frame = capture.read()
            if not ok:
                break

            if (frame_index - start_frame) % frame_step == 0:
                gray = analysis_gray(frame, analysis_width)
                if previous_gray is not None:
                    samples.append(
                        MotionSample(
                            time_seconds=frame_index / source_fps,
                            magnitude=flow_magnitude(previous_gray, gray),
                        )
                    )
                previous_gray = gray

            frame_index += 1
    finally:
        capture.release()

    return samples


def build_motion_anchors(samples: list[MotionSample], time_range: TimeRange) -> list[EditAnchor]:
    anchors = [
        EditAnchor(type="clip_start", time_seconds=time_range.start_seconds, confidence=1.0, reason="Shot boundary start."),
        EditAnchor(type="clip_end", time_seconds=time_range.end_seconds, confidence=1.0, reason="Shot boundary end."),
    ]
    if not samples:
        return anchors

    magnitudes = np.array([sample.magnitude for sample in samples], dtype=np.float32)
    peak_index = int(np.argmax(magnitudes))
    peak = samples[peak_index]
    peak_value = float(magnitudes[peak_index])
    if peak_value <= 1e-6:
        return anchors

    threshold = peak_value * 0.35
    onset_index = peak_index
    while onset_index > 0 and magnitudes[onset_index - 1] >= threshold:
        onset_index -= 1

    settle_index = peak_index
    while settle_index + 1 < len(samples) and magnitudes[settle_index + 1] >= threshold:
        settle_index += 1

    anchors.extend(
        [
            EditAnchor(
                type="motion_onset",
                time_seconds=samples[onset_index].time_seconds,
                confidence=0.72,
                reason="Motion rises into the dominant gesture around this shot boundary candidate.",
            ),
            EditAnchor(
                type="motion_peak",
                time_seconds=peak.time_seconds,
                confidence=0.88,
                reason="Highest sampled local optical-flow magnitude in the shot.",
            ),
            EditAnchor(
                type="motion_settle",
                time_seconds=samples[settle_index].time_seconds,
                confidence=0.68,
                reason="Dominant motion falls back below the gesture threshold.",
            ),
        ]
    )
    return anchors
