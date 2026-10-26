from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from .analysis_cache import (
    DEFAULT_ADAPTIVE_THRESHOLD,
    DEFAULT_ANALYSIS_WIDTH,
    DEFAULT_MIN_SCENE_LEN_FRAMES,
    DEFAULT_SAMPLE_FPS,
    load_cached_analysis,
    write_cached_analysis,
)
from .analysis_models import GlobalMotionSample, MotionSample, ShotAnalysis, TimeRange, VirProject
from .global_motion import estimate_pair, summarize_global_motion
from .models import MediaAsset, MonterProject
from .motion import analysis_gray, build_motion_anchors, flow_magnitude
from .proxy import proxy_path_for
from .shots import detect_shots


def sample_motion_signals(
    video_path: Path,
    time_range: TimeRange,
    sample_fps: float = DEFAULT_SAMPLE_FPS,
    analysis_width: int = DEFAULT_ANALYSIS_WIDTH,
) -> tuple[list[MotionSample], list[GlobalMotionSample]]:
    """Extract local flow and global camera motion from the same decoded frames."""
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

    motion_samples: list[MotionSample] = []
    global_samples: list[GlobalMotionSample] = []
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
                    timestamp = frame_index / source_fps
                    motion_samples.append(
                        MotionSample(
                            time_seconds=timestamp,
                            magnitude=flow_magnitude(previous_gray, gray),
                        )
                    )
                    estimate = estimate_pair(previous_gray, gray)
                    if estimate is not None:
                        tx, ty, rotation, scale, inlier_ratio = estimate
                        global_samples.append(
                            GlobalMotionSample(
                                time_seconds=timestamp,
                                translation_x=tx,
                                translation_y=ty,
                                rotation_degrees=rotation,
                                scale=scale,
                                inlier_ratio=inlier_ratio,
                            )
                        )
                previous_gray = gray

            frame_index += 1
    finally:
        capture.release()

    return motion_samples, global_samples


def analyze_asset(asset: MediaAsset, proxy_path: Path) -> list[ShotAnalysis]:
    shots = detect_shots(
        proxy_path,
        adaptive_threshold=DEFAULT_ADAPTIVE_THRESHOLD,
        min_scene_len_frames=DEFAULT_MIN_SCENE_LEN_FRAMES,
    )
    analyses: list[ShotAnalysis] = []

    for index, shot_range in enumerate(shots):
        samples, global_samples = sample_motion_signals(proxy_path, shot_range)
        magnitudes = [sample.magnitude for sample in samples]
        analyses.append(
            ShotAnalysis(
                id=f"shot_{asset.id}_{index:04d}",
                asset_id=asset.id,
                range=shot_range,
                mean_motion=float(np.mean(magnitudes)) if magnitudes else 0.0,
                peak_motion=max(magnitudes, default=0.0),
                motion_samples=samples,
                edit_anchors=build_motion_anchors(samples, shot_range),
                global_motion=summarize_global_motion(global_samples),
            )
        )

    return analyses


def analyze_project(
    project: MonterProject,
    proxy_dir: Path,
    cache_dir: Path | None = None,
) -> VirProject:
    shots: list[ShotAnalysis] = []
    warnings: list[str] = []

    for asset in project.assets:
        proxy = proxy_path_for(asset, proxy_dir)
        if not proxy.exists():
            warnings.append(f"Proxy missing for {asset.id}; asset skipped.")
            continue
        try:
            cached = load_cached_analysis(asset, proxy, cache_dir) if cache_dir is not None else None
            if cached is not None:
                shots.extend(cached)
                continue

            asset_shots = analyze_asset(asset, proxy)
            shots.extend(asset_shots)
            if cache_dir is not None:
                write_cached_analysis(asset, proxy, cache_dir, asset_shots)
        except Exception as exc:  # keep a long ingest usable if one codec/clip is broken
            warnings.append(f"Analysis failed for {asset.id}: {exc}")

    return VirProject.new(project.project_id, shots=shots, warnings=warnings)
