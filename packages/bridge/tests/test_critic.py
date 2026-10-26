from monter_bridge.analysis_models import ShotAnalysis, TimeRange, VirProject
from monter_bridge.critic import critique_edit
from monter_bridge.ctl_models import CtlClip, CtlProgram, CtlTransition
from monter_bridge.planning_models import EditPlan, EditSegment


def segment(id_: str, shot_id: str, start: float, end: float, target: float, actual: float, confidence: float = .8) -> EditSegment:
    return EditSegment(
        id=id_, asset_id=shot_id, shot_id=shot_id,
        source_in_seconds=0, source_out_seconds=end-start,
        timeline_in_seconds=start, timeline_out_seconds=end,
        role="build", target_energy=target, shot_energy=actual,
        confidence=confidence, reason="fixture",
    )


def fixture_vir() -> VirProject:
    return VirProject.new("p", [
        ShotAnalysis(id="a", asset_id="a", range=TimeRange(start_seconds=0, end_seconds=4), mean_motion=.2, peak_motion=.3, motion_samples=[], edit_anchors=[]),
        ShotAnalysis(id="b", asset_id="b", range=TimeRange(start_seconds=0, end_seconds=4), mean_motion=2, peak_motion=3, motion_samples=[], edit_anchors=[]),
    ])


def test_critic_flags_repetition_and_energy_without_aggregate_score():
    edit = EditPlan(
        project_id="p", target_duration_seconds=4, actual_duration_seconds=4,
        segments=[segment("s1", "a", 0, 2, .9, .1), segment("s2", "a", 2, 4, .8, .1, .3)],
    )
    ctl = CtlProgram(
        project_id="p", duration_seconds=4,
        clips=[
            CtlClip(id="s1", asset_id="a", shot_id="a", source_in_seconds=0, source_out_seconds=2, timeline_in_seconds=0, timeline_out_seconds=2),
            CtlClip(id="s2", asset_id="a", shot_id="a", source_in_seconds=0, source_out_seconds=2, timeline_in_seconds=2, timeline_out_seconds=4),
        ],
        transitions=[CtlTransition(boundary_index=1, mechanism="hard_cut", reason="fixture")],
    )

    report = critique_edit(edit, ctl, fixture_vir())
    codes = {finding.code for finding in report.findings}
    metric_names = {metric.name for metric in report.metrics}

    assert report.status == "needs_revision"
    assert "immediate_repetition" in codes
    assert "energy_mismatch" in codes
    assert "low_confidence_selection" in codes
    assert "aggregate_score" not in metric_names
