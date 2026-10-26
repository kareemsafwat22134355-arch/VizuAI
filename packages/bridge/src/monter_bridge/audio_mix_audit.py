from __future__ import annotations

import re
import subprocess
from pathlib import Path

from .audio_mix_models import AudioMixAudit

MEAN_VOLUME_RE = re.compile(r"mean_volume:\s*(-?\d+(?:\.\d+)?)\s*dB")
MAX_VOLUME_RE = re.compile(r"max_volume:\s*(-?\d+(?:\.\d+)?)\s*dB")
DEFAULT_SAFE_THRESHOLD_DBFS = -0.5


def audit_audio_mix(path: Path, safety_threshold_dbfs: float = DEFAULT_SAFE_THRESHOLD_DBFS) -> AudioMixAudit:
    if not path.is_file():
        raise FileNotFoundError(f"Rendered media does not exist: {path}")
    completed = subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
            "-map", "0:a:0", "-af", "volumedetect", "-f", "null", "-",
        ],
        capture_output=True,
        text=True,
    )
    stderr = completed.stderr
    if completed.returncode != 0:
        raise ValueError(f"Could not audit rendered audio mix: {stderr.strip()}")

    mean_match = MEAN_VOLUME_RE.search(stderr)
    max_match = MAX_VOLUME_RE.search(stderr)
    if mean_match is None or max_match is None:
        raise ValueError("FFmpeg volumedetect did not report mean_volume/max_volume; rendered file may not contain usable audio")

    mean_volume = float(mean_match.group(1))
    max_volume = float(max_match.group(1))
    return AudioMixAudit(
        path_label=path.name,
        mean_volume_dbfs=mean_volume,
        max_volume_dbfs=max_volume,
        clipping_safe=max_volume <= safety_threshold_dbfs,
        safety_threshold_dbfs=safety_threshold_dbfs,
        notes=[
            "Audit measures decoded AAC sample peak with FFmpeg volumedetect; it is not an inter-sample true-peak meter.",
            "The render graph uses a lookahead limiter before AAC encoding, and this post-encode audit verifies the decoded result still retains headroom.",
        ],
    )
