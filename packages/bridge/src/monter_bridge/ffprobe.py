from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .models import MediaTechnical


def parse_fraction(value: str | None) -> float | None:
    if not value or value in {"0/0", "N/A"}:
        return None
    if "/" not in value:
        try:
            return float(value)
        except ValueError:
            return None
    numerator, denominator = value.split("/", 1)
    try:
        denominator_value = float(denominator)
        return float(numerator) / denominator_value if denominator_value else None
    except ValueError:
        return None


def parse_probe_payload(payload: dict) -> MediaTechnical:
    streams = payload.get("streams", [])
    video = next((stream for stream in streams if stream.get("codec_type") == "video"), {})
    audio = next((stream for stream in streams if stream.get("codec_type") == "audio"), None)
    format_info = payload.get("format", {})

    try:
        duration = float(format_info.get("duration", 0) or 0)
    except (TypeError, ValueError):
        duration = 0.0

    return MediaTechnical(
        duration_seconds=max(duration, 0.0),
        width=video.get("width"),
        height=video.get("height"),
        fps=parse_fraction(video.get("avg_frame_rate") or video.get("r_frame_rate")),
        codec=video.get("codec_name"),
        has_audio=audio is not None,
    )


def probe_media(path: Path) -> MediaTechnical:
    command = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration:stream=codec_type,codec_name,width,height,avg_frame_rate,r_frame_rate",
        "-of", "json", str(path),
    ]
    completed = subprocess.run(command, check=True, capture_output=True, text=True)
    return parse_probe_payload(json.loads(completed.stdout))
