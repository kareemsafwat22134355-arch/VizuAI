from monter_bridge.analysis_models import EditAnchor, ShotAnalysis, TimeRange, VirProject
from monter_bridge.ctl import compile_ctl
from monter_bridge.planning_models import EditPlan, EditSegment


def test_compile_ctl_motivates_motion_peak_cut():
    shot_a = ShotAnalysis(
        id="shot_a",
        asset_id="asset_a",
        range=TimeRange(start_seconds=0, end_seconds=3),
        mean_motion=1,
        peak_motion=2,
        motion_samples=[],
        edit_anchors=[EditAnchor(type="motion_peak", time_seconds=1.9, confidence=0.9, reason="peak")],
    )
    shot_b = ShotAnalysis(
        id="shot_b",
        asset_id="asset_b",
        range=TimeRange(start_seconds=0, end_seconds=3),
        mean_motion=0.5,
        peak_motion=1,
        motion_samples=[],
        edit_anchors=[],
    )
    vir = VirProject.new("p", [shot_a, shot_b])
    edit = EditPlan(
        project_id="p",
        target_duration_seconds=4,
        actual_duration_seconds=4,
        segments=[
            EditSegment(id="s1", asset_id="asset_a", shot_id="shot_a", source_in_seconds=0, source_out_seconds=2, timeline_in_seconds=0, timeline_out_seconds=2, role="build", target_energy=.5, shot_energy=.6, confidence=.9, reason="x"),
            EditSegment(id="s2", asset_id="asset_b", shot_id="shot_b", source_in_seconds=0, source_out_seconds=2, timeline_in_seconds=2, timeline_out_seconds=4, role="reveal", target_energy=.5, shot_energy=.4, confidence=.8, reason="y"),
        ],
    )

    ctl = compile_ctl(edit, vir)

    assert ctl.schema_version == "ctl-0.1"
    assert len(ctl.clips) == 2
    assert ctl.transitions[0].mechanism == "motion_peak_cut"
    assert ctl.transitions[0].duration_seconds == 0
