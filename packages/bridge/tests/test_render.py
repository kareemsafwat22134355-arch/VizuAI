from pathlib import Path

from monter_bridge.ctl_models import CtlClip, CtlProgram, CtlTransition
from monter_bridge.models import MediaAsset, MonterProject
from monter_bridge.render import render_command


def fixture_project() -> MonterProject:
    return MonterProject(
        project_id="p",
        project_name="Render Test",
        created_at="2026-10-26T00:00:00Z",
        source_root_label="RAW",
        source_bytes=20,
        proxy_bytes=10,
        assets=[
            MediaAsset(id="a", filename="A.mov", source_rel_path="A.mov", source_size_bytes=10, duration_seconds=4, width=1920, height=1080, fps=25, codec="h264", has_audio=True),
            MediaAsset(id="b", filename="B.mov", source_rel_path="B.mov", source_size_bytes=10, duration_seconds=4, width=1920, height=1080, fps=25, codec="h264", has_audio=True),
        ],
    )


def fixture_ctl() -> CtlProgram:
    return CtlProgram(
        project_id="p",
        duration_seconds=4,
        clips=[
            CtlClip(id="s1", asset_id="a", shot_id="sa", source_in_seconds=.5, source_out_seconds=2.5, timeline_in_seconds=0, timeline_out_seconds=2),
            CtlClip(id="s2", asset_id="b", shot_id="sb", source_in_seconds=1, source_out_seconds=3, timeline_in_seconds=2, timeline_out_seconds=4),
        ],
        transitions=[CtlTransition(boundary_index=1, mechanism="hard_cut", reason="fixture")],
        render_fps=24,
        render_width=960,
    )


def test_render_command_compiles_trim_scale_and_concat():
    command = render_command(fixture_ctl(), fixture_project(), Path("proxies"), Path("out.mp4"))
    joined = " ".join(command)
    assert "asset_" not in joined
    assert "trim=start=0.500000:end=2.500000" in joined
    assert "concat=n=2:v=1:a=0" in joined
    assert "scale=w=960:h=540" in joined
    assert "-an" in command
    assert command[-1] == "out.mp4"


def test_render_command_maps_optional_music():
    command = render_command(fixture_ctl(), fixture_project(), Path("proxies"), Path("out.mp4"), Path("music.wav"))
    joined = " ".join(command)
    assert "-stream_loop -1 -i music.wav" in joined
    assert "-map 2:a:0" in joined
    assert "afade=t=out" in joined
