from __future__ import annotations

import hashlib
import json
import shutil
from functools import lru_cache
from pathlib import Path
from typing import Protocol

import cv2
import numpy as np

from .advanced_analysis_models import SourceAnalysisWindow
from .segmentation_models import (
    SegmentationBackendDescriptor,
    SegmentationFrameArtifact,
    SegmentationSide,
    SegmentationWindowArtifact,
)


class SegmentationBackend(Protocol):
    descriptor: SegmentationBackendDescriptor

    def segment(self, frame_bgr: np.ndarray, *, time_seconds: float) -> np.ndarray:
        """Return one 2D foreground mask aligned to frame_bgr."""
        ...


@lru_cache(maxsize=64)
def _content_digest_cached(path_text: str, size_bytes: int, mtime_ns: int) -> str:
    digest = hashlib.blake2s(digest_size=16)
    with Path(path_text).open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _proxy_content_digest(video_path: Path) -> str:
    resolved = video_path.resolve()
    stat = resolved.stat()
    return _content_digest_cached(str(resolved), stat.st_size, stat.st_mtime_ns)


def _cache_key(
    video_path: Path,
    window: SourceAnalysisWindow,
    side: SegmentationSide,
    backend: SegmentationBackendDescriptor,
    sample_fps: float,
    analysis_width: int,
) -> str:
    stat = video_path.stat()
    payload = {
        "proxyDigest": _proxy_content_digest(video_path),
        "proxySizeBytes": stat.st_size,
        "segmentId": window.segment_id,
        "assetId": window.asset_id,
        "shotId": window.shot_id,
        "side": side,
        "sourceStartSeconds": round(window.source_start_seconds, 6),
        "sourceEndSeconds": round(window.source_end_seconds, 6),
        "sampleFps": round(sample_fps, 6),
        "analysisWidth": analysis_width,
        "backend": backend.model_dump(by_alias=True, mode="json"),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "seg_" + hashlib.blake2s(raw, digest_size=12).hexdigest()


def _resize_frame(frame: np.ndarray, analysis_width: int) -> np.ndarray:
    height, width = frame.shape[:2]
    if width <= analysis_width:
        return frame
    scale = analysis_width / width
    return cv2.resize(
        frame,
        (analysis_width, max(1, round(height * scale))),
        interpolation=cv2.INTER_AREA,
    )


def _sample_window_frames(
    video_path: Path,
    window: SourceAnalysisWindow,
    sample_fps: float,
    analysis_width: int,
) -> list[tuple[float, np.ndarray]]:
    if sample_fps <= 0:
        raise ValueError("segmentation sample_fps must be > 0")
    if analysis_width < 64:
        raise ValueError("segmentation analysis_width must be >= 64")

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise ValueError(f"Could not open proxy for segmentation: {video_path}")

    source_fps = capture.get(cv2.CAP_PROP_FPS) or 24.0
    frame_step = max(1, round(source_fps / sample_fps))
    start_frame = max(0, round(window.source_start_seconds * source_fps))
    end_frame = max(start_frame, round(window.source_end_seconds * source_fps))
    capture.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    frames: list[tuple[float, np.ndarray]] = []
    frame_index = start_frame
    try:
        while frame_index <= end_frame:
            ok, frame = capture.read()
            if not ok:
                break
            if (frame_index - start_frame) % frame_step == 0:
                frames.append((frame_index / source_fps, _resize_frame(frame, analysis_width)))
            frame_index += 1
    finally:
        capture.release()
    return frames


def _normalize_mask(mask: np.ndarray, expected_shape: tuple[int, int]) -> np.ndarray:
    array = np.asarray(mask)
    if array.ndim != 2:
        raise ValueError("segmentation backend must return a 2D mask")
    if array.shape != expected_shape:
        raise ValueError(
            f"segmentation mask shape {array.shape} does not match frame shape {expected_shape}"
        )
    if not np.issubdtype(array.dtype, np.number) and array.dtype != np.bool_:
        raise ValueError("segmentation mask must be numeric or boolean")
    return (array > 0).astype(np.uint8) * 255


def _bbox_xywh_norm(mask_u8: np.ndarray) -> list[float] | None:
    ys, xs = np.where(mask_u8 > 0)
    if not len(xs):
        return None
    height, width = mask_u8.shape
    x0, x1 = int(xs.min()), int(xs.max())
    y0, y1 = int(ys.min()), int(ys.max())
    return [
        x0 / width,
        y0 / height,
        (x1 - x0 + 1) / width,
        (y1 - y0 + 1) / height,
    ]


def _load_cached(
    cache_root: Path,
    cache_key: str,
    descriptor: SegmentationBackendDescriptor,
) -> SegmentationWindowArtifact | None:
    manifest = cache_root / cache_key / "manifest.json"
    if not manifest.is_file():
        return None
    try:
        artifact = SegmentationWindowArtifact.model_validate_json(manifest.read_text(encoding="utf-8"))
    except Exception:
        return None
    if artifact.cache_key != cache_key or artifact.backend != descriptor:
        return None

    root = cache_root.resolve()
    for frame in artifact.frames:
        candidate = (cache_root / frame.mask_path).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            return None
        if not candidate.is_file():
            return None
    return artifact.model_copy(update={"cache_hit": True})


def execute_segmentation_window(
    video_path: Path,
    window: SourceAnalysisWindow,
    side: SegmentationSide,
    cache_root: Path,
    backend: SegmentationBackend,
    *,
    sample_fps: float = 6.0,
    analysis_width: int = 320,
) -> SegmentationWindowArtifact:
    descriptor = SegmentationBackendDescriptor.model_validate(backend.descriptor)
    key = _cache_key(video_path, window, side, descriptor, sample_fps, analysis_width)
    cache_root.mkdir(parents=True, exist_ok=True)

    cached = _load_cached(cache_root, key, descriptor)
    if cached is not None:
        return cached

    sampled = _sample_window_frames(video_path, window, sample_fps, analysis_width)
    final_dir = cache_root / key
    temporary_dir = cache_root / f".{key}.tmp"
    if temporary_dir.exists():
        shutil.rmtree(temporary_dir)
    temporary_dir.mkdir(parents=True, exist_ok=True)

    frames: list[SegmentationFrameArtifact] = []
    try:
        for index, (time_seconds, frame) in enumerate(sampled):
            raw_mask = backend.segment(frame, time_seconds=time_seconds)
            mask = _normalize_mask(raw_mask, frame.shape[:2])
            filename = f"mask-{index:04d}.png"
            output = temporary_dir / filename
            if not cv2.imwrite(str(output), mask):
                raise ValueError(f"Could not write segmentation mask artifact: {output}")
            foreground_fraction = float(np.count_nonzero(mask)) / float(mask.size)
            frames.append(SegmentationFrameArtifact(
                time_seconds=time_seconds,
                mask_path=f"{key}/{filename}",
                width=mask.shape[1],
                height=mask.shape[0],
                foreground_fraction=foreground_fraction,
                bbox_xywh_norm=_bbox_xywh_norm(mask),
            ))

        artifact = SegmentationWindowArtifact(
            segment_id=window.segment_id,
            asset_id=window.asset_id,
            shot_id=window.shot_id,
            side=side,
            source_start_seconds=window.source_start_seconds,
            source_end_seconds=window.source_end_seconds,
            sample_fps=sample_fps,
            analysis_width=analysis_width,
            backend=descriptor,
            cache_key=key,
            cache_hit=False,
            frames=frames,
        )
        (temporary_dir / "manifest.json").write_text(
            artifact.model_dump_json(by_alias=True, indent=2),
            encoding="utf-8",
        )
        if final_dir.exists():
            shutil.rmtree(final_dir)
        temporary_dir.replace(final_dir)
        return artifact
    except Exception:
        shutil.rmtree(temporary_dir, ignore_errors=True)
        raise
