from __future__ import annotations

import json
from pathlib import Path

from .analysis_models import ShotAnalysis
from .models import MediaAsset

ANALYSIS_CACHE_VERSION = 1
ANALYSIS_ALGORITHM_VERSION = "motion-global-occlusion-v3"
DEFAULT_SAMPLE_FPS = 4.0
DEFAULT_ANALYSIS_WIDTH = 320
DEFAULT_ADAPTIVE_THRESHOLD = 3.0
DEFAULT_MIN_SCENE_LEN_FRAMES = 12


def analysis_fingerprint(proxy_path: Path) -> dict[str, object]:
    stat = proxy_path.stat()
    return {
        "cacheVersion": ANALYSIS_CACHE_VERSION,
        "algorithmVersion": ANALYSIS_ALGORITHM_VERSION,
        "proxySizeBytes": stat.st_size,
        "proxyMtimeNs": stat.st_mtime_ns,
        "sampleFps": DEFAULT_SAMPLE_FPS,
        "analysisWidth": DEFAULT_ANALYSIS_WIDTH,
        "adaptiveThreshold": DEFAULT_ADAPTIVE_THRESHOLD,
        "minSceneLenFrames": DEFAULT_MIN_SCENE_LEN_FRAMES,
    }


def cache_path_for(asset: MediaAsset, cache_dir: Path) -> Path:
    return cache_dir / f"{asset.id}.analysis.json"


def load_cached_analysis(asset: MediaAsset, proxy_path: Path, cache_dir: Path) -> list[ShotAnalysis] | None:
    path = cache_path_for(asset, cache_dir)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    if payload.get("fingerprint") != analysis_fingerprint(proxy_path):
        return None
    shots = payload.get("shots")
    if not isinstance(shots, list):
        return None
    try:
        return [ShotAnalysis.model_validate(shot) for shot in shots]
    except Exception:
        return None


def write_cached_analysis(asset: MediaAsset, proxy_path: Path, cache_dir: Path, shots: list[ShotAnalysis]) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_path_for(asset, cache_dir)
    temporary = path.with_suffix(path.suffix + ".tmp")
    payload = {
        "fingerprint": analysis_fingerprint(proxy_path),
        "shots": [shot.model_dump(by_alias=True, mode="json") for shot in shots],
    }
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(path)
    return path
