import pytest

from monter_bridge.audio_edit import build_audio_edit_plan
from monter_bridge.audio_edit_models import AudioBoundaryIntent
from monter_bridge.ctl_models import CtlClip, CtlProgram, CtlTransition, TimeWarpIntent, TimeWarpSlice
from monter_bridge.models import MediaAsset, MonterProject


def project(has_incoming_audio: bool = True) -> MonterProject:
    return MonterProject(
        project_id="p", project_name="Audio Fixture", created_at="2026-10-26T00:00:00Z",
        source_root_label="RAW", source_bytes=20, proxy_bytes=10,
        assets=[
            MediaAsset(id="a", filename="a.mp4", source_rel_path="a.mp4", source_size_bytes=10, duration_seconds=4, width=320, height=180, fps=24, codec="h264", has_audio=True),
            MediaAsset(id="b", filename="b.mp4", source_rel_path="b.mp4", source_size_bytes=10, duration_seconds=4, width=320, height=180, fps=24, codec="h264", has_audio=has_incoming_audio),
        ],
    )


def ctl() -> CtlProgram:
    return CtlProgram(
        project_id="p", duration_seconds=4,
        clips=[
            CtlClip(id="s1", asset_id="a", shot_id="sa", source_in_seconds=.5, source_out_seconds=2.5, timeline_in_seconds=0, timeline_out_seconds=2),
            CtlClip(id="s2", asset_id="b", shot_id="sb", source_in_seconds=1.0, source_out_seconds=3.0, timeline_in_seconds=2, timeline_out_seconds=4),
        ],
        transitions=[CtlTransition(boundary_index=1, mechanism="hard_cut", reason="fixture")],
    )


def test_j_cut_moves_incoming_audio_before_picture_without_moving_video():
    program = ctl()
    plan = build_audio_edit_plan(
        project(), program,
        [AudioBoundaryIntent(boundary_index=1, kind="j_cut", overlap_seconds=.25, reason="incoming audio leads")],
    )
    incoming = next(event for event in plan.events if event.segment_id == "s2")
    assert incoming.source_in_seconds == .75
    assert incoming.timeline_in_seconds == 1.75
    assert incoming.source_out_seconds == 3.0
    assert incoming.timeline_out_seconds == 4.0
    assert program.clips[1].timeline_in_seconds == 2.0


def test_l_cut_extends_outgoing_audio_after_picture_cut():
    plan = build_audio_edit_plan(
        project(), ctl(),
        [AudioBoundaryIntent(boundary_index=1, kind="l_cut", overlap_seconds=.25, reason="outgoing audio trails")],
    )
    outgoing = next(event for event in plan.events if event.segment_id == "s1")
    assert outgoing.source_out_seconds == 2.75
    assert outgoing.timeline_out_seconds == 2.25
    assert outgoing.source_in_seconds == .5


def test_j_cut_requires_incoming_audio_stream():
    with pytest.raises(ValueError, match="incoming source audio"):
        build_audio_edit_plan(
            project(has_incoming_audio=False), ctl(),
            [AudioBoundaryIntent(boundary_index=1, kind="j_cut", overlap_seconds=.2, reason="fixture")],
        )


def test_j_cut_rejects_insufficient_source_handle():
    program = ctl()
    program.clips[1].source_in_seconds = .1
    program.clips[1].source_out_seconds = 2.1
    with pytest.raises(ValueError, match="insufficient incoming"):
        build_audio_edit_plan(
            project(), program,
            [AudioBoundaryIntent(boundary_index=1, kind="j_cut", overlap_seconds=.2, reason="fixture")],
        )


def test_l_cut_rejects_insufficient_source_handle():
    program = ctl()
    program.clips[0].source_out_seconds = 3.9
    program.clips[0].source_in_seconds = 1.9
    with pytest.raises(ValueError, match="insufficient outgoing"):
        build_audio_edit_plan(
            project(), program,
            [AudioBoundaryIntent(boundary_index=1, kind="l_cut", overlap_seconds=.2, reason="fixture")],
        )


def test_timewarped_segment_audio_is_omitted_and_cannot_drive_j_cut():
    program = ctl()
    program.time_warps = [TimeWarpIntent(
        segment_id="s2", anchor_seconds=2.5, reason="fixture",
        slices=[
            TimeWarpSlice(source_in_seconds=1.0, source_out_seconds=1.7, playback_rate=.8),
            TimeWarpSlice(source_in_seconds=1.7, source_out_seconds=2.2, playback_rate=1.5),
            TimeWarpSlice(source_in_seconds=2.2, source_out_seconds=3.0, playback_rate=1.0),
        ],
    )]
    with pytest.raises(ValueError, match="incoming source audio"):
        build_audio_edit_plan(
            project(), program,
            [AudioBoundaryIntent(boundary_index=1, kind="j_cut", overlap_seconds=.2, reason="fixture")],
        )
