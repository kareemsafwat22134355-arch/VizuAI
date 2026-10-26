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
                    pair_mean_magnitudes.append(mean_magnitude)
                    pair_p90_magnitudes.append(p90_magnitude)
                    pair_dx.append(dx)
                    pair_dy.append(dy)
                    pair_coherence.append(coherence)
                previous_gray = gray
            frame_index += 1
    finally:
        capture.release()

    return DenseFlowWindowSummary(
        segment_id=window.segment_id,
        asset_id=window.asset_id,
        shot_id=window.shot_id,
        source_start_seconds=window.source_start_seconds,
        source_end_seconds=window.source_end_seconds,
        sample_count=len(pair_mean_magnitudes),
        mean_magnitude=float(np.mean(pair_mean_magnitudes)) if pair_mean_magnitudes else 0.0,
        p90_magnitude=float(np.mean(pair_p90_magnitudes)) if pair_p90_magnitudes else 0.0,
        mean_dx=float(np.mean(pair_dx)) if pair_dx else 0.0,
        mean_dy=float(np.mean(pair_dy)) if pair_dy else 0.0,
        directional_coherence=float(np.mean(pair_coherence)) if pair_coherence else 0.0,
    )


def _direction_compatibility(left: DenseFlowWindowSummary, right: DenseFlowWindowSummary) -> float:
    left_norm = math.hypot(left.mean_dx, left.mean_dy)
    right_norm = math.hypot(right.mean_dx, right.mean_dy)
    if left_norm <= 1e-6 or right_norm <= 1e-6:
        return 0.5
    cosine = (left.mean_dx * right.mean_dx + left.mean_dy * right.mean_dy) / (left_norm * right_norm)
    return max(0.0, min(1.0, (cosine + 1.0) / 2.0))


def execute_advanced_analysis(
    project: MonterProject,
    plan: AdvancedAnalysisPlan,
    proxy_dir: Path,
    sample_fps: float = 12.0,
    analysis_width: int = 320,
) -> AdvancedAnalysisResults:
    if project.project_id != plan.project_id:
        raise ValueError("Project manifest projectId does not match advanced analysis plan")

    assets = {asset.id: asset for asset in project.assets}
    results: list[BoundaryExecutionResult] = []

    for request in plan.requests:
        boundary = BoundaryExecutionResult(boundary_index=request.boundary_index, priority=request.priority)
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
                feature_results.append(FeatureExecutionResult(
                    feature="dense_flow",
                    status="completed" if completed else "failed",
                    backend="opencv-farneback",
                    reason=(
                        "Dense optical flow executed only inside the scheduler-selected source windows."
                        if completed
                        else "Dense optical flow could not produce at least one frame pair on both selected windows."
                    ),
                    metrics={
                        "leftSampleCount": left_flow.sample_count,
                        "rightSampleCount": right_flow.sample_count,
                        "leftMeanMagnitude": left_flow.mean_magnitude,
                        "rightMeanMagnitude": right_flow.mean_magnitude,
                        "directionCompatibility": compatibility,
                    },
                ))
            except Exception as exc:
                feature_results.append(FeatureExecutionResult(
                    feature="dense_flow",
                    status="failed",
                    backend="opencv-farneback",
                    reason=str(exc),
                ))

        for feature in request.requested_features:
            if feature == "dense_flow":
                continue
            feature_results.append(FeatureExecutionResult(
                feature=feature,
                status="backend_unavailable",
                backend="unconfigured",
                reason=f"{feature} was requested by the scheduler, but v0.17 does not install or execute a heavyweight backend automatically.",
            ))

        boundary.features = feature_results
        results.append(boundary)

    return AdvancedAnalysisResults(
        project_id=project.project_id,
        boundaries=results,
        notes=[
            "Dense flow uses OpenCV Farneback only on scheduler-selected windows; it is a deterministic CPU baseline, not RAFT.",
            "Depth and segmentation requests remain explicit backend_unavailable results until real optional backends are configured.",
            "No heavyweight model is downloaded automatically by this executor.",
        ],
    )
