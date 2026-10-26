from __future__ import annotations

import subprocess
from pathlib import Path

from .ctl_models import CtlProgram, TimeWarpIntent
from .models import MediaAsset, MonterProject
from .proxy import proxy_path_for


def _video_filters_for_clip(input_index: int, clip, warp: TimeWarpIntent | None, width: int, height: int, fps: int) -> list[str]:
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
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,fps={fps},format=yuv420p[v{input_index}]"
    )
    return filters


def _atempo_chain(rate: float) -> str:
    factors: list[float] = []
    remaining = rate
    while remaining > 2.0:
        factors.append(2.0)
        remaining /= 2.0
    while remaining < 0.5:
        factors.append(0.5)
        remaining /= 0.5
    factors.append(remaining)
    return ",".join(f"atempo={factor:.9f}" for factor in factors)


def _audio_shifts(ctl: CtlProgram) -> dict[str, tuple[float, float]]:
    shifts = {clip.id: [0.0, 0.0] for clip in ctl.clips}  # start shift, end shift
    for intent in ctl.audio_boundaries:
        left_index = intent.boundary_index - 1
        right_index = intent.boundary_index
        if left_index < 0 or right_index >= len(ctl.clips):
            continue
        left = ctl.clips[left_index]
        right = ctl.clips[right_index]
        offset = intent.offset_seconds
        if intent.mechanism == "l_cut":
            shifts[left.id][1] += offset
            shifts[right.id][0] += offset
        elif intent.mechanism == "j_cut":
            shifts[left.id][1] -= offset
            shifts[right.id][0] -= offset
    return {clip_id: (values[0], values[1]) for clip_id, values in shifts.items()}


def _audio_filters_for_clip(
    input_index: int,
    clip,
    asset: MediaAsset,
    warp: TimeWarpIntent | None,
    shifts: tuple[float, float],
) -> list[str]:
    start_shift, end_shift = shifts
    nominal_duration = clip.timeline_out_seconds - clip.timeline_in_seconds + end_shift - start_shift
    if not asset.has_audio:
        return [
            f"anullsrc=r=48000:cl=stereo,atrim=duration={max(0.01, nominal_duration):.6f},"
            f"asetpts=PTS-STARTPTS[a{input_index}]"
        ]

    # Audio boundary offsets are deliberately not synthesized next to timewarped clips.
    # This keeps source sound physically aligned with the same retime mapping as picture.
    if warp is not None:
        slice_labels: list[str] = []
        filters: list[str] = []
        for slice_index, slice_ in enumerate(warp.slices):
            label = f"atw{input_index}_{slice_index}"
            slice_labels.append(f"[{label}]")
            filters.append(
                f"[{input_index}:a]atrim=start={slice_.source_in_seconds:.6f}:end={slice_.source_out_seconds:.6f},"
                f"asetpts=PTS-STARTPTS,{_atempo_chain(slice_.playback_rate)},"
                f"aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo[{label}]"
            )
        filters.append("".join(slice_labels) + f"concat=n={len(slice_labels)}:v=0:a=1[a{input_index}]")
        return filters

    start = max(0.0, clip.source_in_seconds + start_shift)
    end = min(asset.duration_seconds, clip.source_out_seconds + end_shift)
    if end <= start:
        return [f"anullsrc=r=48000:cl=stereo,atrim=duration={max(0.01, nominal_duration):.6f},asetpts=PTS-STARTPTS[a{input_index}]"]
    return [
        f"[{input_index}:a]atrim=start={start:.6f}:end={end:.6f},asetpts=PTS-STARTPTS,"
        f"aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo[a{input_index}]"
    ]


def render_command(
    ctl: CtlProgram,
    project: MonterProject,
    proxy_dir: Path,
    output: Path,
    music: Path | None = None,
    use_source_audio: bool = False,
) -> list[str]:
    if not ctl.clips:
        raise ValueError("CTL contains no clips")

    assets = {asset.id: asset for asset in project.assets}
    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    clip_assets: list[MediaAsset] = []
    for clip in ctl.clips:
        asset = assets.get(clip.asset_id)
        if asset is None:
            raise ValueError(f"CTL references unknown asset: {clip.asset_id}")
        clip_assets.append(asset)
        command.extend(["-i", str(proxy_path_for(asset, proxy_dir))])

    music_index: int | None = None
    if music:
        music_index = len(ctl.clips)
        command.extend(["-stream_loop", "-1", "-i", str(music)])

    height = max(180, round(ctl.render_width * 9 / 16))
    warp_by_segment = {warp.segment_id: warp for warp in ctl.time_warps}
    filters: list[str] = []
    video_labels: list[str] = []
    for index, clip in enumerate(ctl.clips):
        filters.extend(_video_filters_for_clip(index, clip, warp_by_segment.get(clip.id), ctl.render_width, height, ctl.render_fps))
        video_labels.append(f"[v{index}]")
    filters.append("".join(video_labels) + f"concat=n={len(video_labels)}:v=1:a=0[vout]")

    source_audio_label: str | None = None
    if use_source_audio:
        shifts = _audio_shifts(ctl)
        audio_labels: list[str] = []
        for index, (clip, asset) in enumerate(zip(ctl.clips, clip_assets)):
            filters.extend(_audio_filters_for_clip(index, clip, asset, warp_by_segment.get(clip.id), shifts[clip.id]))
            audio_labels.append(f"[a{index}]")
        filters.append("".join(audio_labels) + f"concat=n={len(audio_labels)}:v=0:a=1[sourceaudio]")
        source_audio_label = "[sourceaudio]"

    audio_map: str | None = None
    if source_audio_label and music_index is not None:
        filters.extend([
            f"{source_audio_label}volume={ctl.source_audio_gain:.3f}[srcmix]",
            f"[{music_index}:a:0]atrim=0:{ctl.duration_seconds:.6f},asetpts=PTS-STARTPTS,volume={ctl.music_gain:.3f}[musicmix]",
            f"[srcmix][musicmix]amix=inputs=2:duration=first:normalize=0,afade=t=out:st={max(0.0, ctl.duration_seconds - 0.6):.3f}:d=0.6[aout]",
        ])
        audio_map = "[aout]"
    elif source_audio_label:
        filters.append(f"{source_audio_label}volume={ctl.source_audio_gain:.3f},afade=t=out:st={max(0.0, ctl.duration_seconds - 0.4):.3f}:d=0.4[aout]")
        audio_map = "[aout]"

    command.extend(["-filter_complex", ";".join(filters), "-map", "[vout]"])
    if audio_map:
        command.extend(["-map", audio_map, "-c:a", "aac", "-b:a", "160k"])
    elif music_index is not None:
        command.extend([
            "-map", f"{music_index}:a:0", "-c:a", "aac", "-b:a", "160k",
            "-af", f"volume={ctl.music_gain:.3f},afade=t=out:st={max(0.0, ctl.duration_seconds - 0.6):.3f}:d=0.6",
        ])
    else:
        command.append("-an")

    command.extend([
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "24",
        "-movflags", "+faststart", "-t", f"{ctl.duration_seconds:.6f}", str(output),
    ])
    return command


def render_draft(
    ctl: CtlProgram,
    project: MonterProject,
    proxy_dir: Path,
    output: Path,
    music: Path | None = None,
    use_source_audio: bool = False,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(render_command(ctl, project, proxy_dir, output, music, use_source_audio), check=True)
