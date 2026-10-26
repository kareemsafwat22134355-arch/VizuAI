from monter_bridge.models import MediaAsset, MonterProject
from monter_bridge.planning_models import EditPlan, EditSegment
from monter_bridge.sound import select_audio_boundaries


def asset(id_: str, duration: float = 8) -> MediaAsset:
    return MediaAsset(
        id=id_, filename=f"{id_}.mov", source_rel_path=f"{id_}.mov", source_size_bytes=10,
        duration_seconds=duration, width=1920, height=1080, fps=25, codec="h264", has_audio=True,
    )


def segment(id_: str, asset_id: str, tin: float, tout: float, role: str, source_in: float = 1, source_out: float = 3) -> EditSegment:
    return EditSegment(
        id=id_, asset_id=asset_id, shot_id=f"shot_{id_}",
        source_in_seconds=source_in, source_out_seconds=source_out,
        timeline_in_seconds=tin, timeline_out_seconds=tout,
        role=role, target_energy=.5, shot_energy=.5, confidence=.8, reason="fixture",
    )


def test_reveal_boundary_can_become_real_l_cut_when_handles_exist():
    project = MonterProject(
        project_id="p", project_name="Sound", created_at="2026-10-26T00:00:00Z",
        source_root_label="RAW", source_bytes=20, proxy_bytes=0, assets=[asset("a"), asset("b")],
    )
    edit = EditPlan(
        project_id="p", target_duration_seconds=4, actual_duration_seconds=4,
        segments=[segment("s1", "a", 0, 2, "rupture"), segment("s2", "b", 2, 4, "reveal")],
    )

    intents = select_audio_boundaries(edit, project, [], max_intents=1)

    assert len(intents) == 1
    assert intents[0].mechanism == "l_cut"
    assert intents[0].boundary_index == 1
    assert intents[0].offset_seconds > 0


def test_audio_boundary_is_not_added_next_to_timewarp():
    from monter_bridge.ctl_models import TimeWarpIntent, TimeWarpSlice
    project = MonterProject(
        project_id="p", project_name="Sound", created_at="2026-10-26T00:00:00Z",
        source_root_label="RAW", source_bytes=20, proxy_bytes=0, assets=[asset("a"), asset("b")],
    )
    edit = EditPlan(project_id="p", target_duration_seconds=4, actual_duration_seconds=4, segments=[segment("s1", "a", 0, 2, "rupture"), segment("s2", "b", 2, 4, "reveal")])
    warp = TimeWarpIntent(segment_id="s1", anchor_seconds=2, reason="event", slices=[
        TimeWarpSlice(source_in_seconds=1, source_out_seconds=2, playback_rate=1),
        TimeWarpSlice(source_in_seconds=2, source_out_seconds=3, playback_rate=1),
    ])
    assert select_audio_boundaries(edit, project, [warp]) == []
