from __future__ import annotations

import hashlib
from collections.abc import Callable
from pathlib import Path

from .ffprobe import probe_media
from .models import MediaAsset, MediaTechnical, MonterProject

VIDEO_EXTENSIONS = {".mp4", ".mov", ".mxf", ".mkv", ".avi", ".mts", ".m2ts", ".webm"}


def discover_media(folder: Path) -> list[Path]:
    return [
        path
        for path in sorted(folder.rglob("*"))
        if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS
    ]


def asset_id(path: Path, source_root: Path) -> str:
    relative = path.resolve().relative_to(source_root.resolve()).as_posix()
    return "asset_" + hashlib.blake2s(relative.encode("utf-8"), digest_size=8).hexdigest()


def ingest_project(
    folder: Path,
    project_name: str,
    probe: Callable[[Path], MediaTechnical] = probe_media,
) -> MonterProject:
    root = folder.resolve()
    if not root.exists() or not root.is_dir():
        raise ValueError(f"Source folder does not exist: {root}")

    assets: list[MediaAsset] = []
    for path in discover_media(root):
        technical = probe(path)
        assets.append(
            MediaAsset(
                id=asset_id(path, root),
                filename=path.name,
                source_path=str(path),
                source_size_bytes=path.stat().st_size,
                duration_seconds=technical.duration_seconds,
                width=technical.width,
                height=technical.height,
                fps=technical.fps,
                codec=technical.codec,
                has_audio=technical.has_audio,
            )
        )

    project_seed = f"{root}|{project_name}".encode("utf-8")
    project_id = "project_" + hashlib.blake2s(project_seed, digest_size=8).hexdigest()
    return MonterProject.new(project_id, project_name, root, assets)
