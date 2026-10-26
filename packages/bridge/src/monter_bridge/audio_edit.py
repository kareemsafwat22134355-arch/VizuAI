from __future__ import annotations

from .audio_edit_models import AudioBoundaryIntent, AudioEditPlan, SourceAudioEvent
from .ctl_models import CtlProgram
from .models import MonterProject


def build_audio_edit_plan(
    project: MonterProject,
    ctl: CtlProgram,
    boundary_intents: list[AudioBoundaryIntent] | None = None,
    source_gain_db: float = -3.0,
    music_gain_db: float = -8.0,
) -> AudioEditPlan:
    if project.project_id != ctl.project_id:
        raise ValueError("Project manifest projectId does not match CTL")

    assets = {asset.id: asset for asset in project.assets}
    warped_segments = {intent.segment_id for intent in ctl.time_warps}
    events_by_segment: dict[str, SourceAudioEvent] = {}
    notes: list[str] = [
        "Source audio is mapped independently from picture so J/L cuts can cross visual boundaries without moving video edits.",
        "v0.19 keeps source audio at 1x playback and omits timewarped picture segments until explicit audio-retime semantics exist.",
    ]

    for clip in ctl.clips:
        asset = assets.get(clip.asset_id)
        if asset is None:
            raise ValueError(f"CTL references unknown asset: {clip.asset_id}")
        if not asset.has_audio:
            notes.append(f"Segment {clip.id} has no source audio stream and was omitted from the source-audio timeline.")
            continue
        if clip.id in warped_segments:
            notes.append(f"Segment {clip.id} is timewarped; source audio was omitted rather than silently drifting out of sync.")
            continue

        source_duration = clip.source_out_seconds - clip.source_in_seconds
        timeline_duration = clip.timeline_out_seconds - clip.timeline_in_seconds
        if abs(source_duration - timeline_duration) > 0.005:
            raise ValueError(
                f"Segment {clip.id} source/timeline duration differs without an audio-retime contract: "
                f"source={source_duration:.6f}s timeline={timeline_duration:.6f}s"
            )
        events_by_segment[clip.id] = SourceAudioEvent(
            id=f"audio_{clip.id}",
            segment_id=clip.id,
            asset_id=clip.asset_id,
            source_in_seconds=clip.source_in_seconds,
            source_out_seconds=clip.source_out_seconds,
            timeline_in_seconds=clip.timeline_in_seconds,
            timeline_out_seconds=clip.timeline_out_seconds,
            gain_db=source_gain_db,
            reason="Synchronous source audio for the selected picture segment.",
        )

    intents = sorted(boundary_intents or [], key=lambda item: item.boundary_index)
    transition_boundaries = {transition.boundary_index for transition in ctl.transitions}
    clip_by_id = {clip.id: clip for clip in ctl.clips}

    for intent in intents:
        if intent.boundary_index not in transition_boundaries:
            raise ValueError(f"Audio intent references unknown visual boundary {intent.boundary_index}")
        left_index = intent.boundary_index - 1
        right_index = intent.boundary_index
        if left_index < 0 or right_index >= len(ctl.clips):
            raise ValueError(f"Audio boundary {intent.boundary_index} is outside CTL clip range")
        left_clip = ctl.clips[left_index]
        right_clip = ctl.clips[right_index]

        if intent.kind == "sync":
            continue
        if intent.kind == "j_cut":
            event = events_by_segment.get(right_clip.id)
            if event is None:
                raise ValueError(f"J-cut boundary {intent.boundary_index} requires usable incoming source audio")
            if event.source_in_seconds < intent.overlap_seconds - 1e-9:
                raise ValueError(f"J-cut boundary {intent.boundary_index} has insufficient incoming source-audio handle")
            if event.timeline_in_seconds < intent.overlap_seconds - 1e-9:
                raise ValueError(f"J-cut boundary {intent.boundary_index} would start before timeline zero")
            event.source_in_seconds -= intent.overlap_seconds
            event.timeline_in_seconds -= intent.overlap_seconds
            event.reason = intent.reason
            continue

        if intent.kind == "l_cut":
            event = events_by_segment.get(left_clip.id)
            if event is None:
                raise ValueError(f"L-cut boundary {intent.boundary_index} requires usable outgoing source audio")
            asset = assets[event.asset_id]
            if event.source_out_seconds + intent.overlap_seconds > asset.duration_seconds + 1e-9:
                raise ValueError(f"L-cut boundary {intent.boundary_index} has insufficient outgoing source-audio handle")
            if event.timeline_out_seconds + intent.overlap_seconds > ctl.duration_seconds + 1e-9:
                raise ValueError(f"L-cut boundary {intent.boundary_index} would extend beyond timeline duration")
            event.source_out_seconds += intent.overlap_seconds
            event.timeline_out_seconds += intent.overlap_seconds
            event.reason = intent.reason
            continue

    # Pydantic assignment validation is intentionally avoided in PortableModel, so rebuild
    # events through validation after applying independent J/L handle extensions.
    validated_events = [SourceAudioEvent.model_validate(event.model_dump()) for event in events_by_segment.values()]
    return AudioEditPlan(
        project_id=project.project_id,
        duration_seconds=ctl.duration_seconds,
        events=validated_events,
        boundaries=intents,
        music_gain_db=music_gain_db,
        notes=notes,
    )
