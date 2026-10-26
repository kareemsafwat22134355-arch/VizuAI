from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from .director import energy_at
from .ffprobe import probe_media
from .motion import analysis_gray
from .planning_models import DirectorPlan
from .render_analysis_models import RenderAnalysisFinding, RenderAnalysisReport, RenderEnergyBin

BLACK_MEAN_THRESHOLD = 0.025
BLACK_STD_THRESHOLD = 0.020
FREEZE_DIFF_THRESHOLD = 0.0015
ENERGY_WARNING_THRESHOLD = 0.45


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def analyze_render(
    path: Path,
    project_id: str,
    expected_duration_seconds: float,
    director_plan: DirectorPlan,
    sample_fps: float = 4.0,
    analysis_width: int = 320,
) -> RenderAnalysisReport:
    if sample_fps <= 0:
        raise ValueError("sample_fps must be > 0")
    if analysis_width < 64:
        raise ValueError("analysis_width must be >= 64")
    if expected_duration_seconds <= 0:
        raise ValueError("expected_duration_seconds must be > 0")
    if not path.is_file():
        raise FileNotFoundError(f"Rendered media does not exist: {path}")

    technical = probe_media(path)
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise ValueError(f"Could not open rendered media for re-analysis: {path}")

    source_fps = capture.get(cv2.CAP_PROP_FPS) or technical.fps or 24.0
    frame_step = max(1, round(source_fps / sample_fps))
    sampled_times: list[float] = []
    lumas: list[float] = []
    black_flags: list[bool] = []
    pair_times: list[float] = []
    pair_motion_raw: list[float] = []
    freeze_flags: list[bool] = []

    previous_gray: np.ndarray | None = None
    previous_sample_time: float | None = None
    current_freeze_seconds = 0.0
    longest_freeze_seconds = 0.0
    frame_index = 0

    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            if frame_index % frame_step != 0:
                frame_index += 1
                continue

            time_seconds = frame_index / source_fps
            gray = analysis_gray(frame, analysis_width)
            mean_luma = float(np.mean(gray) / 255.0)
            std_luma = float(np.std(gray) / 255.0)
            is_black = mean_luma <= BLACK_MEAN_THRESHOLD and std_luma <= BLACK_STD_THRESHOLD

            sampled_times.append(time_seconds)
            lumas.append(_clamp01(mean_luma))
            black_flags.append(is_black)

            if previous_gray is not None and previous_sample_time is not None:
                difference = float(np.mean(cv2.absdiff(previous_gray, gray)) / 255.0)
                is_freeze = difference <= FREEZE_DIFF_THRESHOLD
                pair_times.append(time_seconds)
                pair_motion_raw.append(max(0.0, difference))
                freeze_flags.append(is_freeze)
                pair_duration = max(0.0, time_seconds - previous_sample_time)
                if is_freeze:
                    current_freeze_seconds += pair_duration
                    longest_freeze_seconds = max(longest_freeze_seconds, current_freeze_seconds)
                else:
                    current_freeze_seconds = 0.0

            previous_gray = gray
            previous_sample_time = time_seconds
            frame_index += 1
    finally:
        capture.release()

    findings: list[RenderAnalysisFinding] = []
    duration_drift = technical.duration_seconds - expected_duration_seconds
    duration_tolerance = max(0.12, 2.0 / max(source_fps, 1.0))

    if abs(duration_drift) > duration_tolerance:
        findings.append(RenderAnalysisFinding(
            code="duration_drift",
            severity="error",
            message=(
                f"Rendered duration drifted by {duration_drift:+.3f}s from the expected "
                f"{expected_duration_seconds:.3f}s timeline (tolerance {duration_tolerance:.3f}s)."
            ),
        ))

    if not sampled_times:
        findings.append(RenderAnalysisFinding(
            code="no_decoded_frames",
            severity="error",
            message="The final media could not produce any sampled video frames during re-analysis.",
        ))

    black_fraction = float(np.mean(black_flags)) if black_flags else 0.0
    freeze_fraction = float(np.mean(freeze_flags)) if freeze_flags else 0.0

    if black_fraction >= 0.98 and sampled_times:
        findings.append(RenderAnalysisFinding(
            code="near_black_render",
            severity="error",
            message=f"{black_fraction:.0%} of sampled render frames are near-black; the output may be catastrophically blank.",
        ))
    elif black_fraction >= 0.60:
        findings.append(RenderAnalysisFinding(
            code="high_black_occupancy",
            severity="warning",
            message=f"{black_fraction:.0%} of sampled render frames are near-black; review whether this is intentional.",
        ))

    freeze_warning_threshold = max(1.5, expected_duration_seconds * 0.50)
    if longest_freeze_seconds >= freeze_warning_threshold:
        findings.append(RenderAnalysisFinding(
            code="long_freeze_span",
            severity="warning",
            message=(
                f"The sampled render contains an approximately {longest_freeze_seconds:.2f}s near-identical frame span. "
                "This may be intentional, but it should be reviewed before automatic revision is trusted."
            ),
        ))

    if pair_motion_raw:
        motion_array = np.asarray(pair_motion_raw, dtype=np.float32)
        p95 = float(np.percentile(motion_array, 95))
        if p95 <= 1e-9:
            normalized_motion = np.zeros_like(motion_array)
        else:
            normalized_motion = np.clip(motion_array / p95, 0.0, 1.0)
    else:
        normalized_motion = np.asarray([], dtype=np.float32)

    bin_count = min(12, max(4, round(expected_duration_seconds * 2.0)))
    bin_edges = np.linspace(0.0, expected_duration_seconds, bin_count + 1)
    energy_bins: list[RenderEnergyBin] = []
    target_values: list[float] = []
    actual_values: list[float] = []

    sampled_times_array = np.asarray(sampled_times, dtype=np.float32) if sampled_times else np.asarray([], dtype=np.float32)
    luma_array = np.asarray(lumas, dtype=np.float32) if lumas else np.asarray([], dtype=np.float32)
    black_array = np.asarray(black_flags, dtype=np.float32) if black_flags else np.asarray([], dtype=np.float32)
    pair_times_array = np.asarray(pair_times, dtype=np.float32) if pair_times else np.asarray([], dtype=np.float32)
    freeze_array = np.asarray(freeze_flags, dtype=np.float32) if freeze_flags else np.asarray([], dtype=np.float32)

    for index in range(bin_count):
        start = float(bin_edges[index])
        end = float(bin_edges[index + 1])
        is_last = index == bin_count - 1
        frame_mask = (
            (sampled_times_array >= start) & (sampled_times_array <= end if is_last else sampled_times_array < end)
            if sampled_times_array.size else np.asarray([], dtype=bool)
        )
        pair_mask = (
            (pair_times_array >= start) & (pair_times_array <= end if is_last else pair_times_array < end)
            if pair_times_array.size else np.asarray([], dtype=bool)
        )
        actual_motion = float(np.mean(normalized_motion[pair_mask])) if pair_mask.size and np.any(pair_mask) else 0.0
        mean_luma = float(np.mean(luma_array[frame_mask])) if frame_mask.size and np.any(frame_mask) else 0.0
        bin_black = float(np.mean(black_array[frame_mask])) if frame_mask.size and np.any(frame_mask) else 0.0
        bin_freeze = float(np.mean(freeze_array[pair_mask])) if pair_mask.size and np.any(pair_mask) else 0.0
        midpoint = (start + end) / 2.0
        target = _clamp01(energy_at(director_plan, midpoint / expected_duration_seconds))
        actual_motion = _clamp01(actual_motion)
        target_values.append(target)
        actual_values.append(actual_motion)
        energy_bins.append(RenderEnergyBin(
            index=index,
            start_seconds=start,
            end_seconds=end,
            mean_motion=actual_motion,
            mean_luma=_clamp01(mean_luma),
            black_fraction=_clamp01(bin_black),
            freeze_fraction=_clamp01(bin_freeze),
            target_energy=target,
        ))

    if target_values:
        energy_alignment = _clamp01(1.0 - float(np.mean(np.abs(np.asarray(actual_values) - np.asarray(target_values)))))
    else:
        energy_alignment = 0.0

    if sampled_times and energy_alignment < ENERGY_WARNING_THRESHOLD:
        findings.append(RenderAnalysisFinding(
            code="energy_curve_mismatch",
            severity="warning",
            message=(
                f"Cheap render-motion energy aligns {energy_alignment:.0%} with the Director curve. "
                "Treat this as diagnostic evidence only; motion magnitude is not narrative energy."
            ),
        ))

    status = "needs_review" if any(finding.severity == "error" for finding in findings) else "pass"
    mean_motion = float(np.mean(normalized_motion)) if normalized_motion.size else 0.0
    peak_motion = float(np.max(normalized_motion)) if normalized_motion.size else 0.0

    return RenderAnalysisReport(
        project_id=project_id,
        path_label=path.name,
        status=status,
        duration_seconds=technical.duration_seconds,
        expected_duration_seconds=expected_duration_seconds,
        duration_drift_seconds=duration_drift,
        has_audio=technical.has_audio,
        sampled_frames=len(sampled_times),
        mean_motion=_clamp01(mean_motion),
        peak_motion=_clamp01(peak_motion),
        black_frame_fraction=_clamp01(black_fraction),
        freeze_pair_fraction=_clamp01(freeze_fraction),
        longest_freeze_seconds=max(0.0, longest_freeze_seconds),
        energy_alignment=energy_alignment,
        energy_bins=energy_bins,
        findings=findings,
        notes=[
            "v0.23 re-analyzes the encoded final render at low resolution/sample rate; it is a physical/integrity pass, not semantic video understanding.",
            "Duration/decode/near-black failures can mark the render needs_review. Long freezes and energy mismatch are warnings only in this milestone.",
            "Energy alignment compares normalized frame-difference motion to the Director curve and must not be interpreted as a complete measure of narrative energy.",
        ],
    )
