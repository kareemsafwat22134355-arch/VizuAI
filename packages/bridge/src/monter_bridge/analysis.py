from __future__ import annotations

from pathlib import Path

import numpy as np

from .analysis_models import ShotAnalysis, VirProject
from .models import MediaAsset, MonterProject
from .motion import build_motion_anchors, sample_motion
from .proxy import proxy_path_for
from .shots import detect_shots


def analyze_asset(asset: MediaAsset, proxy_path: Path) -> list[ShotAnalysis]:
    shots = detect_shots(proxy_path)
    analyses: list[ShotAnalysis] = []

    for index, shot_range in enumerate(shots):
        samples = sample_motion(proxy_path, shot_range)
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
            )
        )

    return analyses


def analyze_project(project: MonterProject, proxy_dir: Path) -> VirProject:
    shots: list[ShotAnalysis] = []
    warnings: list[str] = []

    for asset in project.assets:
        proxy = proxy_path_for(asset, proxy_dir)
        if not proxy.exists():
            warnings.append(f"Proxy missing for {asset.id}; asset skipped.")
            continue
        try:
            shots.extend(analyze_asset(asset, proxy))
        except Exception as exc:  # keep a long ingest usable if one codec/clip is broken
            warnings.append(f"Analysis failed for {asset.id}: {exc}")

    return VirProject.new(project.project_id, shots=shots, warnings=warnings)
