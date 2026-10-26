from __future__ import annotations

import subprocess
from pathlib import Path

from .ctl_models import CtlProgram
from .models import MonterProject
from .proxy import proxy_path_for


def render_command(
    ctl: CtlProgram,
    project: MonterProject,
    proxy_dir: Path,
    output: Path,
    music: Path | None = None,
) -> list[str]:
    if not ctl.clips:
        raise ValueError("CTL contains no clips")

    assets = {asset.id: asset for asset in project.assets}
    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]

    for clip in ctl.clips:
        asset = assets.get(clip.asset_id)
        if asset is None:
            raise ValueError(f"CTL references unknown asset: {clip.asset_id}")
        proxy = proxy_path_for(asset, proxy_dir)
        command.extend(["-i", str(proxy)])

    music_index: int | None = None
    if music:
        music_index = len(ctl.clips)
        command.extend(["-stream_loop", "-1", "-i", str(music)])

    height = max(180, round(ctl.render_width * 9 / 16))
    filters: list[str] = []
    labels: list[str] = []
    for index, clip in enumerate(ctl.clips):
        label = f"v{index}"
        labels.append(f"[{label}]")
        filters.append(
            f"[{index}:v]trim=start={clip.source_in_seconds:.6f}:end={clip.source_out_seconds:.6f},"
            f"setpts=PTS-STARTPTS,"
            f"scale=w={ctl.render_width}:h={height}:force_original_aspect_ratio=decrease,"
            f"pad={ctl.render_width}:{height}:(ow-iw)/2:(oh-ih)/2,"
            f"fps={ctl.render_fps},format=yuv420p[{label}]"
        )
    filters.append("".join(labels) + f"concat=n={len(labels)}:v=1:a=0[vout]")

    command.extend(["-filter_complex", ";".join(filters), "-map", "[vout]"])
    if music_index is not None:
        command.extend([
            "-map", f"{music_index}:a:0",
            "-c:a", "aac", "-b:a", "160k",
            "-af", f"volume=0.75,afade=t=out:st={max(0.0, ctl.duration_seconds - 0.6):.3f}:d=0.6",
        ])
    else:
        command.append("-an")

    command.extend([
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "24",
        "-movflags", "+faststart",
        "-t", f"{ctl.duration_seconds:.6f}",
        str(output),
    ])
    return command


def render_draft(
    ctl: CtlProgram,
    project: MonterProject,
    proxy_dir: Path,
    output: Path,
    music: Path | None = None,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(render_command(ctl, project, proxy_dir, output, music), check=True)
