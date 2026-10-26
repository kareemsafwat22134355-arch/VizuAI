from __future__ import annotations

import subprocess
from pathlib import Path

from .ctl_models import CtlProgram, CtlTransition, TimeWarpIntent
from .models import MonterProject
from .proxy import proxy_path_for


def _clip_extensions(ctl: CtlProgram) -> tuple[list[float], list[float]]:
    before = [0.0 for _ in ctl.clips]
    after = [0.0 for _ in ctl.clips]
    for transition in ctl.transitions:
        if transition.duration_seconds <= 0:
            continue
        left_index = transition.boundary_index - 1
        right_index = transition.boundary_index
        if left_index < 0 or right_index >= len(ctl.clips):
            raise ValueError(f"CTL transition boundary is out of range: {transition.boundary_index}")
        half = transition.duration_seconds / 2.0
        after[left_index] += half
        before[right_index] += half
    return before, after


def _video_filters_for_clip(
    input_index: int,
    clip,
    warp: TimeWarpIntent | None,
    width: int,
    height: int,
    fps: int,
    extend_before: float = 0.0,
    extend_after: float = 0.0,
) -> list[str]:
    filters: list[str] = []
    source_label = f"base{input_index}"

    if warp is not None and (extend_before > 1e-9 or extend_after > 1e-9):
        raise ValueError("Non-zero transition handles cannot be combined with an adjacent timewarp in the deterministic renderer")

    if warp is None:
        source_in = clip.source_in_seconds - extend_before
        source_out = clip.source_out_seconds + extend_after
        if source_in < -1e-6:
            raise ValueError(f"Transition handle would trim before source zero for clip {clip.id}")
        filters.append(
            f"[{input_index}:v]trim=start={max(0.0, source_in):.6f}:end={source_out:.6f},"
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
        f"fps={fps},settb=AVTB,format=yuv420p[v{input_index}]"
    )
    return filters


def _directional_xfade_name(transition: CtlTransition) -> str:
    direction = str(transition.parameters.get("screenDirection", ""))
    mapping = {
        "left": "slideleft",
        "right": "slideright",
        "up": "slideup",
        "down": "slidedown",
    }
    if direction not in mapping:
        raise ValueError(f"directional_bridge requires a cardinal screenDirection, got: {direction!r}")
    return mapping[direction]


def _clip_render_duration(clip, extend_before: float, extend_after: float) -> float:
    return (clip.timeline_out_seconds - clip.timeline_in_seconds) + extend_before + extend_after


def _compose_video_filters(
    ctl: CtlProgram,
    clip_durations: list[float],
) -> list[str]:
    if len(ctl.clips) == 1:
        return ["[v0]null[vout]"]

    transition_by_boundary = {transition.boundary_index: transition for transition in ctl.transitions}
    filters: list[str] = []
    current_label = "v0"
    current_duration = clip_durations[0]

    for right_index in range(1, len(ctl.clips)):
        boundary_index = right_index
        transition = transition_by_boundary.get(boundary_index)
        output_label = "vout" if right_index == len(ctl.clips) - 1 else f"join{right_index}"

        if transition is not None and transition.duration_seconds > 0:
            if transition.mechanism != "directional_bridge":
                raise ValueError(f"Renderer does not support non-zero transition mechanism: {transition.mechanism}")
            duration = transition.duration_seconds
            offset = current_duration - duration
            if offset < -1e-6:
                raise ValueError(f"Transition {boundary_index} is longer than the composed outgoing timeline")
            xfade = _directional_xfade_name(transition)
            filters.append(
                f"[{current_label}][v{right_index}]"
                f"xfade=transition={xfade}:duration={duration:.6f}:offset={max(0.0, offset):.6f}"
                f"[{output_label}]"
            )
            current_duration += clip_durations[right_index] - duration
        else:
            filters.append(f"[{current_label}][v{right_index}]concat=n=2:v=1:a=0[{output_label}]")
            current_duration += clip_durations[right_index]

        current_label = output_label

    if abs(current_duration - ctl.duration_seconds) > max(1.0 / ctl.render_fps, 1e-3):
        raise ValueError(
            f"Compiled video duration drifted from CTL: {current_duration:.6f}s vs {ctl.duration_seconds:.6f}s"
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
    extend_before, extend_after = _clip_extensions(ctl)
    filters: list[str] = []
    clip_durations: list[float] = []

    for index, clip in enumerate(ctl.clips):
        filters.extend(_video_filters_for_clip(
            index,
            clip,
            warp_by_segment.get(clip.id),
            ctl.render_width,
            height,
            ctl.render_fps,
            extend_before=extend_before[index],
            extend_after=extend_after[index],
        ))
        clip_durations.append(_clip_render_duration(clip, extend_before[index], extend_after[index]))

    filters.extend(_compose_video_filters(ctl, clip_durations))

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
