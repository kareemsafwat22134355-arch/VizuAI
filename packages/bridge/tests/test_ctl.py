from monter_bridge.analysis_models import EditAnchor, GlobalMotionSummary, ShotAnalysis, TimeRange, VirProject
from monter_bridge.ctl import compile_ctl
from monter_bridge.planning_models import EditPlan, EditSegment


def edit_for(shot_a: ShotAnalysis, shot_b: ShotAnalysis) -> EditPlan:
    return EditPlan(
        project_id="p", target_duration_seconds=4, actual_duration_seconds=4,
        segments=[
            EditSegment(id="s1", asset_id=shot_a.asset_id, shot_id=shot_a.id, source_in_seconds=0, source_out_seconds=2, timeline_in_seconds=0, timeline_out_seconds=2, role="build", target_energy=.5, shot_energy=.6, confidence=.9, reason="x"),
            EditSegment(id="s2", asset_id=shot_b.asset_id, shot_id=shot_b.id, source_in_seconds=0, source_out_seconds=2, timeline_in_seconds=2, timeline_out_seconds=4, role="reveal", target_energy=.5, shot_energy=.4, confidence=.8, reason="y"),
        ],
    )


def test_compile_ctl_motivates_motion_peak_cut():
    shot_a = ShotAnalysis(
        id="shot_a", asset_id="asset_a", range=TimeRange(start_seconds=0, end_seconds=3),
        mean_motion=1, peak_motion=2, motion_samples=[],
        edit_anchors=[EditAnchor(type="motion_peak", time_seconds=1.9, confidence=0.9, reason="peak")],
    )
    shot_b = ShotAnalysis(
        id="shot_b", asset_id="asset_b", range=TimeRange(start_seconds=0, end_seconds=3),
        mean_motion=0.5, peak_motion=1, motion_samples=[], edit_anchors=[],
    )
    ctl = compile_ctl(edit_for(shot_a, shot_b), VirProject.new("p", [shot_a, shot_b]))
    assert ctl.schema_version == "ctl-0.1"
    assert ctl.transitions[0].mechanism == "motion_peak_cut"
    assert ctl.transitions[0].duration_seconds == 0


def test_compile_ctl_prefers_confident_global_motion_match():
    motion = GlobalMotionSummary(dominant_screen_direction="right", zoom_direction="static", confidence=.9)
    shot_a = ShotAnalysis(id="a", asset_id="a", range=TimeRange(start_seconds=0, end_seconds=3), mean_motion=1, peak_motion=2, motion_samples=[], edit_anchors=[], global_motion=motion)
    shot_b = ShotAnalysis(id="b", asset_id="b", range=TimeRange(start_seconds=0, end_seconds=3), mean_motion=1, peak_motion=2, motion_samples=[], edit_anchors=[], global_motion=motion)

    ctl = compile_ctl(edit_for(shot_a, shot_b), VirProject.new("p", [shot_a, shot_b]))

    assert ctl.transitions[0].mechanism == "motion_match_cut"
    assert ctl.transitions[0].relation_score is not None
    assert ctl.transitions[0].evidence["leftDirection"] == "right"
