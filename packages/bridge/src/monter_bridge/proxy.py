from __future__ import annotations

import subprocess
from pathlib import Path


def proxy_command(source: Path, destination: Path, width: int = 960, fps: int = 24) -> list[str]:
    return [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(source),
        "-vf", f"scale='min({width},iw)':-2,fps={fps}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "28",
        "-c:a", "aac", "-b:a", "96k",
        "-movflags", "+faststart",
        str(destination),
    ]


def create_proxy(source: Path, destination: Path, width: int = 960, fps: int = 24) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(proxy_command(source, destination, width, fps), check=True)
