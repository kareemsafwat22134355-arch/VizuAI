from __future__ import annotations

import subprocess
from pathlib import Path

from .models import MediaAsset, MonterProject


def proxy_command(source: Path, destination: Path, width: int = 960, fps: int = 24) -> list[str]:
    return [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(source),
        "-map", "0:v:0", "-map", "0:a?",
        "-sn", "-dn",
        "-vf", f"scale='min({width},iw)':-2,fps={fps}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "28",
        "-c:a", "aac", "-b:a", "96k",
        "-movflags", "+faststart",
        str(destination),
    ]


def create_proxy(
    source: Path,
    destination: Path,
    width: int = 960,
    fps: int = 24,
    skip_if_fresh: bool = True,
) -> bool:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if skip_if_fresh and destination.exists() and destination.stat().st_mtime >= source.stat().st_mtime:
        return False
    subprocess.run(proxy_command(source, destination, width, fps), check=True)
    return True


def proxy_path_for(asset: MediaAsset, out_dir: Path) -> Path:
    return out_dir / f"{asset.id}.mp4"


def create_project_proxies(
    project: MonterProject,
    source_root: Path,
    out_dir: Path,
    width: int = 960,
    fps: int = 24,
) -> tuple[int, int]:
    created = 0
    total_bytes = 0
    for asset in project.assets:
        source = source_root / asset.source_rel_path
        destination = proxy_path_for(asset, out_dir)
        if not source.exists():
            raise FileNotFoundError(f"Missing source media for {asset.id}: {source}")
        if create_proxy(source, destination, width=width, fps=fps):
            created += 1
        if destination.exists():
            total_bytes += destination.stat().st_size

    project.proxy_bytes = total_bytes
    return created, total_bytes
