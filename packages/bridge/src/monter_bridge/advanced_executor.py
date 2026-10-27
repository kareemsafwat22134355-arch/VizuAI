from __future__ import annotations

import math
from pathlib import Path

import cv2
import numpy as np

from .advanced_analysis_models import AdvancedAnalysisPlan, SourceAnalysisWindow
from .advanced_execution_models import (
    AdvancedAnalysisResults,
    BoundaryExecutionResult,
    DenseFlowWindowSummary,
    FeatureExecutionResult,
)
from .models import MonterProject
from .motion import analysis_gray
from .proxy import proxy_path_for
from .segmentation import SegmentationBackend, execute_segmentation_window


def _dense_flow_window(
    video_path: Path,
    window: SourceAnalysisWindow,
    sample_fps: float = 12.0,
    analysis_width: int = 320,
) -> DenseFlowWindowSummary:
    if sample_fps <= 0:
        raise ValueError("sample_fps must be > 0")
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise ValueError(f"Could not open proxy for dense flow: {video_path}")

    source_fps = capture.get(cv2.CAP_PROP_FPS) or 24.0
    frame_step = max(1, round(source_fps / sample_fps))
    start_frame = max(0, round(window.source_start_seconds * source_fps))
    end_frame = max(start_frame, round(window.source_end_seconds * source_fps))
    capture.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    previous_gray: np.ndarray | None = None
    frame_index = start_frame
    pair_times_seconds: list[float] = []
    pair_mean_magnitudes: list[float] = []
    pair_p90_magnitudes: list[float] = []
    pair_dx: list[float] = []
    pair_dy: list[float] = []
    pair_coherence: list[float] = []

    try:
        while frame_index <= end_frame:
            ok, frame = capture.read()
            if not ok:
                break
            if (frame_index - start_frame) % frame_step == 0:
                gray = analysis_gray(frame, analysis_width)
                if previous_gray is not None:
                    flow = cv2.calcOpticalFlowFarneback(
                        previous_gray,
                        gray,
                        None,
                        pyr_scale=0.5,
                        levels=3,
                        winsize=17,
                        iterations=3,
                        poly_n=5,
                        poly_sigma=1.1,
                        flags=0,
                    )
                    magnitude, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
                    mean_magnitude = float(np.mean(magnitude))
                    p90_magnitude = float(np.percentile(magnitude, 90))
                    dx = float(np.median(flow[..., 0]))
                    dy = float(np.median(flow[..., 1]))
                    vector_norm = math.hypot(dx, dy)
                    coherence = min(1.0, vector_norm / (mean_magnitude + 1e-6)) if mean_magnitude > 0 else 0.0
                    pair_times_seconds.append(frame_index / source_fps)
                    pair_mean_magnitudes.append(mean_magnitude)
                    pair_p90_magnitudes.append(p90_magnitude)
                    pair_dx.append(dx)
                    pair_dy.append(dy)
                    pair_coherence.append(coherence)
                previous_gray = gray
            frame_index += 1
    finally:
        capture.release()

    mean_magnitude = float(np.mean(pair_mean_magnitudes)) if pair_mean_magnitudes else 0.0
    peak_magnitude = 0.0
    peak_time_seconds: float | None = None
    onset_time_seconds: float | None = None
    temporal_contrast = 0.0

    if pair_mean_magnitudes:
        peak_index = int(np.argmax(pair_mean_magnitudes))
        peak_magnitude = float(pair_mean_magnitudes[peak_index])
        peak_time_seconds = pair_times_seconds[peak_index]
        temporal_contrast = peak_magnitude / (mean_magnitude + 1e-6) if mean_magnitude > 0 else 0.0
        if peak_magnitude > 1e-6:
            onset_threshold = peak_magnitude * 0.35
            for index in range(peak_index + 1):
                if pair_mean_magnitudes[index] >= onset_threshold:
                    onset_time_seconds = pair_times_seconds[index]
                    break

    return DenseFlowWindowSummary(
        segment_id=window.segment_id,
        asset_id=window.asset_id,
        shot_id=window.shot_id,
        source_start_seconds=window.source_start_seconds,
        source_end_seconds=window.source_end_seconds,
        sample_count=len(pair_mean_magnitudes),
        mean_magnitude=mean_magnitude,
        p90_magnitude=float(np.mean(pair_p90_magnitudes)) if pair_p90_magnitudes else 0.0,
        mean_dx=float(np.mean(pair_dx)) if pair_dx else 0.0,
        mean_dy=float(np.mean(pair_dy)) if pair_dy else 0.0,
        directional_coherence=float(np.mean(pair_coherence)) if pair_coherence else 0.0,
        peak_magnitude=peak_magnitude,
        peak_time_seconds=peak_time_seconds,
        onset_time_seconds=onset_time_seconds,
        temporal_contrast=temporal_contrast,
    )


def _direction_compatibility(left: DenseFlowWindowSummary, right: DenseFlowWindowSummary) -> float:
    left_norm = math.hypot(left.mean_dx, left.mean_dy)
    right_norm = math.hypot(right.mean_dx, right.mean_dy)
    if left_norm <= 1e-6 or right_norm <= 1e-6:
        return 0.5
    cosine = (left.mean_dx * right.mean_dx + left.mean_dy * right.mean_dy) / (left_norm * right_norm)
    return max(0.0, min(1.0, (cosine + 1.0) / 2.0))


def _mean_foreground_fraction(frames) -> float:
    if not frames:
        return 0.0
    return float(np.mean([frame.foreground_fraction for frame in frames]))


def execute_advanced_analysis(
    project: MonterProject,
    plan: AdvancedAnalysisPlan,
    proxy_dir: Path,
    sample_fps: float = 12.0,
    analysis_width: int = 320,
    segmentation_backend: SegmentationBackend | None = None,
    segmentation_cache_dir: Path | None = None,
    segmentation_sample_fps: float = 6.0,
    segmentation_analysis_width: int | None = None,
) -> AdvancedAnalysisResults:
    if project.project_id != plan.project_id:
        raise ValueError("Project manifest projectId does not match advanced analysis plan")
    if segmentation_backend is not None and segmentation_sample_fps <= 0:
        raise ValueError("segmentation_sample_fps must be > 0")

    assets = {asset.id: asset for asset in project.assets}
    results: list[BoundaryExecutionResult] = []
    segmentation_width = segmentation_analysis_width or analysis_width
    segmentation_cache = segmentation_cache_dir or (proxy_dir.parent / "segmentation-cache")

    for request in plan.requests:
        boundary = BoundaryExecutionResult(
            boundary_index=request.boundary_index,
            priority=request.priority,
            request_evidence=dict(request.evidence),
        )
        feature_results: list[FeatureExecutionResult] = []

        if "dense_flow" in request.requested_features:
            try:
                left_asset = assets[request.left_window.asset_id]
                right_asset = assets[request.right_window.asset_id]
                left_proxy = proxy_path_for(left_asset, proxy_dir)
                right_proxy = proxy_path_for(right_asset, proxy_dir)
                if not left_proxy.is_file() or not right_proxy.is_file():
                    missing = [str(path) for path in (left_proxy, right_proxy) if not path.is_file()]
                    raise FileNotFoundError(f"Missing proxy file(s): {', '.join(missing)}")

                left_flow = _dense_flow_window(left_proxy, request.left_window, sample_fps, analysis_width)
                right_flow = _dense_flow_window(right_proxy, request.right_window, sample_fps, analysis_width)
                compatibility = _direction_compatibility(left_flow, right_flow)
                boundary.left_flow = left_flow
                boundary.right_flow = right_flow
                boundary.flow_direction_compatibility = compatibility
                completed = left_flow.sample_count > 0 and right_flow.sample_count > 0
                metrics: dict[str, float | int | str | bool] = {
                    "leftSampleCount": left_flow.sample_count,
                    "rightSampleCount": right_flow.sample_count,
                    "leftMeanMagnitude": left_flow.mean_magnitude,
                    "rightMeanMagnitude": right_flow.mean_magnitude,
                    "leftPeakMagnitude": left_flow.peak_magnitude,
                    "rightPeakMagnitude": right_flow.peak_magnitude,
                    "leftTemporalContrast": left_flow.temporal_contrast,
                    "rightTemporalContrast": right_flow.temporal_contrast,
                    "directionCompatibility": compatibility,
                }
                if left_flow.peak_time_seconds is not None:
                    metrics["leftPeakTimeSeconds"] = left_flow.peak_time_seconds
                if left_flow.onset_time_seconds is not None:
                    metrics["leftOnsetTimeSeconds"] = left_flow.onset_time_seconds
                if right_flow.peak_time_seconds is not None:
                    metrics["rightPeakTimeSeconds"] = right_flow.peak_time_seconds
                if right_flow.onset_time_seconds is not None:
                    metrics["rightOnsetTimeSeconds"] = right_flow.onset_time_seconds
                feature_results.append(FeatureExecutionResult(
                    feature="dense_flow",
                    status="completed" if completed else "failed",
                    backend="opencv-farneback",
                    reason=(
                        "Dense optical flow executed only inside the scheduler-selected source windows, preserving temporal peak/onset evidence for boundary timing."
                        if completed
                        else "Dense optical flow could not produce at least one frame pair on both selected windows."
                    ),
                    metrics=metrics,
                ))
            except Exception as exc:
                feature_results.append(FeatureExecutionResult(
                    feature="dense_flow",
                    status="failed",
                    backend="opencv-farneback",
                    reason=str(exc),
                ))

        if "segmentation" in request.requested_features:
            if segmentation_backend is None:
                feature_results.append(FeatureExecutionResult(
                    feature="segmentation",
                    status="backend_unavailable",
                    backend="unconfigured",
                    reason="Segmentation was requested by the scheduler, but no heavyweight backend is installed or configured automatically.",
                ))
            else:
                try:
                    left_asset = assets[request.left_window.asset_id]
                    right_asset = assets[request.right_window.asset_id]
                    left_proxy = proxy_path_for(left_asset, proxy_dir)
                    right_proxy = proxy_path_for(right_asset, proxy_dir)
                    if not left_proxy.is_file() or not right_proxy.is_file():
                        missing = [str(path) for path in (left_proxy, right_proxy) if not path.is_file()]
                        raise FileNotFoundError(f"Missing proxy file(s): {', '.join(missing)}")

                    left_segmentation = execute_segmentation_window(
                        left_proxy,
                        request.left_window,
                        "left",
                        segmentation_cache,
                        segmentation_backend,
                        sample_fps=segmentation_sample_fps,
                        analysis_width=segmentation_width,
                    )
                    right_segmentation = execute_segmentation_window(
                        right_proxy,
                        request.right_window,
                        "right",
                        segmentation_cache,
                        segmentation_backend,
                        sample_fps=segmentation_sample_fps,
                        analysis_width=segmentation_width,
                    )
                    boundary.left_segmentation = left_segmentation
                    boundary.right_segmentation = right_segmentation
                    completed = bool(left_segmentation.frames) and bool(right_segmentation.frames)
                    feature_results.append(FeatureExecutionResult(
                        feature="segmentation",
                        status="completed" if completed else "failed",
                        backend=left_segmentation.backend.backend_id,
                        reason=(
                            "Configured segmentation backend executed only inside scheduler-selected boundary windows; mask PNGs were stored in the deterministic cache."
                            if completed
                            else "Configured segmentation backend did not produce at least one sampled mask on both boundary windows."
                        ),
                        metrics={
                            "modelId": left_segmentation.backend.model_id,
                            "leftSampleCount": len(left_segmentation.frames),
                            "rightSampleCount": len(right_segmentation.frames),
                            "leftMeanForegroundFraction": _mean_foreground_fraction(left_segmentation.frames),
                            "rightMeanForegroundFraction": _mean_foreground_fraction(right_segmentation.frames),
                            "leftCacheHit": left_segmentation.cache_hit,
                            "rightCacheHit": right_segmentation.cache_hit,
                            "leftCacheKey": left_segmentation.cache_key,
                            "rightCacheKey": right_segmentation.cache_key,
                        },
                    ))
                except Exception as exc:
                    feature_results.append(FeatureExecutionResult(
                        feature="segmentation",
                        status="failed",
                        backend=getattr(getattr(segmentation_backend, "descriptor", None), "backend_id", "configured"),
                        reason=str(exc),
                    ))

        for feature in request.requested_features:
            if feature in {"dense_flow", "segmentation"}:
                continue
            feature_results.append(FeatureExecutionResult(
                feature=feature,
                status="backend_unavailable",
                backend="unconfigured",
                reason=f"{feature} was requested by the scheduler, but no heavyweight backend is installed automatically.",
            ))

        boundary.features = feature_results
        results.append(boundary)

    return AdvancedAnalysisResults(
        project_id=project.project_id,
        boundaries=results,
        notes=[
            "Dense flow uses OpenCV Farneback only on scheduler-selected windows; it is a deterministic CPU baseline, not RAFT.",
            "Dense-flow summaries preserve temporal peak/onset evidence so action-cut timing can be refined instead of using direction averages only.",
            "Segmentation executes only when an explicit backend object is supplied; otherwise requests remain backend_unavailable and no model is downloaded.",
            "Configured segmentation masks are sampled inside scheduler-selected windows and cached as PNG artifacts keyed by media state, window, backend/model version, and sampling parameters.",
            "Depth requests remain backend_unavailable until a real optional backend is configured.",
        ],
    )
