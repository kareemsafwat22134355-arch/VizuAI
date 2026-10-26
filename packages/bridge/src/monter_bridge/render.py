from __future__ import annotations

import subprocess
from pathlib import Path

from .audio_edit_models import AudioEditPlan, SourceAudioEvent
from .ctl_models import CtlProgram, CtlTransition, TimeWarpIntent
from .models import MonterProject
from .proxy import proxy_path_for

AUDIO_LIMITER_LIMIT = 0.80
AUDIO_LIMITER_ATTACK_MS = 5
AUDIO_LIMITER_RELEASE_MS = 50


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


def _source_audio_filter(input_index: int, event_index: int, event: SourceAudioEvent) -> tuple[str, str]:
    duration = event.timeline_out_seconds - event.timeline_in_seconds
    label = f"asrc{event_index}"
    parts = [
        f"[{input_index}:a]atrim=start={event.source_in_seconds:.6f}:end={event.source_out_seconds:.6f}",
        "asetpts=PTS-STARTPTS",
        "aresample=48000",
        "aformat=sample_fmts=fltp:channel_layouts=stereo",
        f"volume={event.gain_db:.3f}dB",
    ]
    if event.fade_in_seconds > 1e-9:
        parts.append(f"afade=t=in:st=0:d={event.fade_in_seconds:.6f}")
    if event.fade_out_seconds > 1e-9:
        fade_out_start = max(0.0, duration - event.fade_out_seconds)
        parts.append(f"afade=t=out:st={fade_out_start:.6f}:d={event.fade_out_seconds:.6f}")
    delay_ms = max(0, round(event.timeline_in_seconds * 1000))
    if delay_ms > 0:
        parts.append(f"adelay={delay_ms}:all=1")
    return ",".join(parts) + f"[{label}]", label


def _final_audio_bus(input_expression: str, duration_seconds: float) -> str:
    return (
        input_expression
        + f"alimiter=limit={AUDIO_LIMITER_LIMIT:.6f}:attack={AUDIO_LIMITER_ATTACK_MS}:"
        f"release={AUDIO_LIMITER_RELEASE_MS}:level=0:latency=1,"
        f"atrim=duration={duration_seconds:.6f}[aout]"
    )


def _audio_filters(
    ctl: CtlProgram,
    project: MonterProject,
    audio_plan: AudioEditPlan | None,
    music_index: int | None,
) -> tuple[list[str], bool]:
    if audio_plan is not None:
        if audio_plan.project_id != ctl.project_id:
            raise ValueError("Audio edit plan projectId does not match CTL")
        if abs(audio_plan.duration_seconds - ctl.duration_seconds) > 1e-3:
            raise ValueError("Audio edit plan duration does not match CTL")

    assets = {asset.id: asset for asset in project.assets}
    clip_input_by_segment = {clip.id: index for index, clip in enumerate(ctl.clips)}
    warped_segments = {warp.segment_id for warp in ctl.time_warps}
    filters: list[str] = []
    mix_labels: list[str] = []

    if audio_plan is not None:
        for event_index, event in enumerate(audio_plan.events):
            input_index = clip_input_by_segment.get(event.segment_id)
            if input_index is None:
                raise ValueError(f"Audio event references unknown CTL segment: {event.segment_id}")
            clip = ctl.clips[input_index]
            if event.asset_id != clip.asset_id:
                raise ValueError(f"Audio event {event.id} asset does not match CTL segment asset")
            asset = assets.get(event.asset_id)
            if asset is None or not asset.has_audio:
                raise ValueError(f"Audio event {event.id} references an asset without source audio")
            if event.segment_id in warped_segments:
                raise ValueError(f"Audio event {event.id} targets a timewarped segment without audio-retime semantics")
            if event.source_out_seconds > asset.duration_seconds + 1e-6:
                raise ValueError(f"Audio event {event.id} extends beyond source duration")
            filter_text, label = _source_audio_filter(input_index, event_index, event)
            filters.append(filter_text)
            mix_labels.append(f"[{label}]")

    if music_index is not None:
        music_gain_db = audio_plan.music_gain_db if audio_plan is not None else -2.5
        filters.append(
            f"[{music_index}:a]atrim=duration={ctl.duration_seconds:.6f},asetpts=PTS-STARTPTS,"
            f"aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
            f"volume={music_gain_db:.3f}dB,"
            f"afade=t=out:st={max(0.0, ctl.duration_seconds - 0.6):.6f}:d=0.600000[musicbed]"
        )
        mix_labels.append("[musicbed]")

    if not mix_labels:
        return filters, False
    if len(mix_labels) == 1:
        filters.append(_final_audio_bus(mix_labels[0], ctl.duration_seconds))
    else:
        filters.append(
            _final_audio_bus(
                "".join(mix_labels)
                + f"amix=inputs={len(mix_labels)}:duration=longest:dropout_transition=0:normalize=0,",
                ctl.duration_seconds,
            )
        )
    return filters, True


def render_command(
    ctl: CtlProgram,
    project: MonterProject,
    proxy_dir: Path,
    output: Path,
    music: Path | None = None,
    audio_plan: AudioEditPlan | None = None,
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
    audio_filters, has_audio_output = _audio_filters(ctl, project, audio_plan, music_index)
    filters.extend(audio_filters)

    command.extend(["-filter_complex", ";".join(filters), "-map", "[vout]"])
    if has_audio_output:
        command.extend(["-map", "[aout]", "-c:a", "aac", "-b:a", "160k"])
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
    audio_plan: AudioEditPlan | None = None,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(render_command(ctl, project, proxy_dir, output, music, audio_plan), check=True)
