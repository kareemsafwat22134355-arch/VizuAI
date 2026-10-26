from __future__ import annotations

import subprocess
from pathlib import Path

from .ctl_models import CtlProgram, TimeWarpIntent
from .models import MonterProject
from .proxy import proxy_path_for


def _video_filters_for_clip(
    input_index: int,
    clip,
    warp: TimeWarpIntent | None,
    width: int,
    height: int,
    fps: int,
) -> list[str]:
    filters: list[str] = []
    source_label = f"base{input_index}"

    if warp is None:
        filters.append(
            f"[{input_index}:v]trim=start={clip.source_in_seconds:.6f}:end={clip.source_out_seconds:.6f},"
            f"setpts=PTS-STARTPTS[{source_label}]"
        )
    else:
        slice_labels: list[str] = []
        for slice_index, slice_ in enumerate(warp.slices):
            label = f"tw{input_index}_{slice_index}"
            slice_labels.append(f"[{label}]")
            filters.append(
                f"[{input_index}:v]trim=start={slice_.source_in_seconds:.6f}:end={slice_.source_out_seconds:.6f},"
                f"setpts=(PTS-STARTPTS)/{slice_.playback_rate:.9f}[{label}]"
            )
        filters.append("".join(slice_labels) + f"concat=n={len(slice_labels)}:v=1:a=0[{source_label}]")

    filters.append(
        f"[{source_label}]scale=w={width}:h={height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,"
        f"fps={fps},format=yuv420p[v{input_index}]"
    )
    return filters


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
        command.extend(["-i", str(proxy_path_for(asset, proxy_dir))])

    music_index: int | None = None
    if music:
        music_index = len(ctl.clips)
        command.extend(["-stream_loop", "-1", "-i", str(music)])

    height = max(180, round(ctl.render_width * 9 / 16))
    warp_by_segment = {warp.segment_id: warp for warp in ctl.time_warps}
    filters: list[str] = []
    labels: list[str] = []
    for index, clip in enumerate(ctl.clips):
        filters.extend(_video_filters_for_clip(
            index,
            clip,
            warp_by_segment.get(clip.id),
            ctl.render_width,
            height,
            ctl.render_fps,
        ))
        labels.append(f"[v{index}]")
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
