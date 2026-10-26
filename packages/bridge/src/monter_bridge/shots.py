from __future__ import annotations

from pathlib import Path

from scenedetect import SceneManager, open_video
from scenedetect.detectors import AdaptiveDetector

from .analysis_models import TimeRange


def detect_shots(video_path: Path, adaptive_threshold: float = 3.0, min_scene_len_frames: int = 12) -> list[TimeRange]:
    video = open_video(str(video_path))
    manager = SceneManager()
    manager.add_detector(
        AdaptiveDetector(
            adaptive_threshold=adaptive_threshold,
            min_scene_len=min_scene_len_frames,
        )
    )
    manager.detect_scenes(video=video)
    scenes = manager.get_scene_list(start_in_scene=True)

    if not scenes:
        duration = video.duration.get_seconds()
        return [TimeRange(start_seconds=0.0, end_seconds=max(0.0, duration))]

    return [
        TimeRange(start_seconds=start.get_seconds(), end_seconds=end.get_seconds())
        for start, end in scenes
    ]
