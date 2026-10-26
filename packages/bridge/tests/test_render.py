from pathlib import Path

from monter_bridge.audio_edit import build_audio_edit_plan
from monter_bridge.audio_edit_models import AudioBoundaryIntent
from monter_bridge.ctl_models import CtlClip, CtlProgram, CtlTransition, TimeWarpIntent, TimeWarpSlice
from monter_bridge.models import MediaAsset, MonterProject
from monter_bridge.render import render_command


def fixture_project() -> MonterProject:
    return MonterProject(
        project_id="p", project_name="Render Test", created_at="2026-10-26T00:00:00Z",
        source_root_label="RAW", source_bytes=20, proxy_bytes=10,
        assets=[
            MediaAsset(id="a", filename="A.mov", source_rel_path="A.mov", source_size_bytes=10, duration_seconds=4, width=1920, height=1080, fps=25, codec="h264", has_audio=True),
            MediaAsset(id="b", filename="B.mov", source_rel_path="B.mov", source_size_bytes=10, duration_seconds=4, width=1920, height=1080, fps=25, codec="h264", has_audio=True),
        ],
    )


def fixture_ctl() -> CtlProgram:
    return CtlProgram(
        project_id="p", duration_seconds=4,
        clips=[
            CtlClip(id="s1", asset_id="a", shot_id="sa", source_in_seconds=.5, source_out_seconds=2.5, timeline_in_seconds=0, timeline_out_seconds=2),
            CtlClip(id="s2", asset_id="b", shot_id="sb", source_in_seconds=1, source_out_seconds=3, timeline_in_seconds=2, timeline_out_seconds=4),
        ],
        transitions=[CtlTransition(boundary_index=1, mechanism="hard_cut", reason="fixture")],
        render_fps=24, render_width=960,
    )


def test_render_command_compiles_trim_scale_and_concat():
    command = render_command(fixture_ctl(), fixture_project(), Path("proxies"), Path("out.mp4"))
    joined = " ".join(command)
    assert "asset_" not in joined
    assert "trim=start=0.500000:end=2.500000" in joined
    assert "concat=n=2:v=1:a=0" in joined
    assert "scale=w=960:h=540" in joined
    assert "settb=AVTB" in joined
    assert "-an" in command
    assert command[-1] == "out.mp4"


def test_render_command_maps_optional_music_through_mix_graph():
    command = render_command(fixture_ctl(), fixture_project(), Path("proxies"), Path("out.mp4"), Path("music.wav"))
    joined = " ".join(command)
    assert "-stream_loop -1 -i music.wav" in joined
    assert "[2:a]atrim=duration=4.000000" in joined
    assert "volume=-2.500dB" in joined
    assert "afade=t=out" in joined
    assert "alimiter=limit=0.800000:attack=5:release=50:level=0:latency=1" in joined
    assert "-map [aout]" in joined


def test_render_command_compiles_real_j_cut_audio_overlap():
    ctl = fixture_ctl()
    plan = build_audio_edit_plan(
        fixture_project(),
        ctl,
        boundary_intents=[AudioBoundaryIntent(boundary_index=1, kind="j_cut", overlap_seconds=.25, reason="incoming sound leads picture")],
    )
    joined = " ".join(render_command(ctl, fixture_project(), Path("proxies"), Path("out.mp4"), audio_plan=plan))

    assert "[0:a]atrim=start=0.500000:end=2.500000" in joined
    assert "[1:a]atrim=start=0.750000:end=3.000000" in joined
    assert "adelay=1750:all=1" in joined
    assert "amix=inputs=2:duration=longest:dropout_transition=0:normalize=0" in joined
    assert "alimiter=limit=0.800000:attack=5:release=50:level=0:latency=1" in joined
    assert "-map [aout]" in joined
    assert "-t 4.000000" in joined


def test_render_command_compiles_timewarp_slices_before_clip_concat():
    ctl = fixture_ctl()
    ctl.time_warps = [TimeWarpIntent(
        segment_id="s1", anchor_seconds=1.5, reason="event",
        slices=[
            TimeWarpSlice(source_in_seconds=.5, source_out_seconds=1.2, playback_rate=.8),
            TimeWarpSlice(source_in_seconds=1.2, source_out_seconds=1.7, playback_rate=1.8),
            TimeWarpSlice(source_in_seconds=1.7, source_out_seconds=2.5, playback_rate=.94),
        ],
    )]
    joined = " ".join(render_command(ctl, fixture_project(), Path("proxies"), Path("out.mp4")))
    assert "setpts=(PTS-STARTPTS)/0.800000000" in joined
    assert "concat=n=3:v=1:a=0[base0]" in joined
    assert "[base0]scale=w=960:h=540" in joined


def test_render_command_uses_symmetric_handles_for_directional_bridge_without_duration_drift():
    ctl = fixture_ctl()
    ctl.transitions = [CtlTransition(
        boundary_index=1,
        mechanism="directional_bridge",
        duration_seconds=.12,
        parameters={"screenDirection": "right"},
        reason="matched motion",
    )]

    command = render_command(ctl, fixture_project(), Path("proxies"), Path("out.mp4"))
    joined = " ".join(command)

    assert "trim=start=0.500000:end=2.560000" in joined
    assert "trim=start=0.940000:end=3.000000" in joined
    assert "xfade=transition=slideright:duration=0.120000:offset=1.940000" in joined
    assert "-t 4.000000" in joined


def test_directional_bridge_rejects_timewarp_overlap_in_renderer():
    ctl = fixture_ctl()
    ctl.transitions = [CtlTransition(
        boundary_index=1,
        mechanism="directional_bridge",
        duration_seconds=.12,
        parameters={"screenDirection": "left"},
        reason="matched motion",
    )]
    ctl.time_warps = [TimeWarpIntent(
        segment_id="s1", anchor_seconds=1.5, reason="event",
        slices=[
            TimeWarpSlice(source_in_seconds=.5, source_out_seconds=1.2, playback_rate=.8),
            TimeWarpSlice(source_in_seconds=1.2, source_out_seconds=1.7, playback_rate=1.8),
            TimeWarpSlice(source_in_seconds=1.7, source_out_seconds=2.5, playback_rate=.94),
        ],
    )]

    try:
        render_command(ctl, fixture_project(), Path("proxies"), Path("out.mp4"))
    except ValueError as exc:
        assert "timewarp" in str(exc).lower()
    else:
        raise AssertionError("expected timewarp + non-zero transition guard")
