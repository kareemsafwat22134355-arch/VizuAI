from monter_bridge.analysis_models import EditAnchor, GlobalMotionSummary, ShotAnalysis, TimeRange, VirProject
from monter_bridge.critic_models import CriticFinding, CriticReport
from monter_bridge.planning_models import EditPlan, EditSegment
from monter_bridge.revision import revise_edit_plan


def test_advanced_action_timing_revision_action_is_tagged_for_verification():
    motion = GlobalMotionSummary(dominant_screen_direction="static", zoom_direction="static", confidence=.9)
    left_shot = ShotAnalysis(
        id="left-shot",
        asset_id="left-asset",
        range=TimeRange(start_seconds=0, end_seconds=4),
        mean_motion=1,
        peak_motion=2,
        motion_samples=[],
        edit_anchors=[EditAnchor(type="motion_peak", time_seconds=1.75, confidence=.9, reason="fixture")],
        global_motion=motion,
    )
    right_shot = ShotAnalysis(
        id="right-shot",
        asset_id="right-asset",
        range=TimeRange(start_seconds=0, end_seconds=4),
        mean_motion=1,
        peak_motion=2,
        motion_samples=[],
        edit_anchors=[],
        global_motion=motion,
    )
    vir = VirProject.new("p", [left_shot, right_shot])
    edit = EditPlan(
        project_id="p",
        target_duration_seconds=4,
        actual_duration_seconds=4,
        segments=[
            EditSegment(
                id="left",
                asset_id="left-asset",
                shot_id="left-shot",
                source_in_seconds=.2,
                source_out_seconds=1.8,
                timeline_in_seconds=0,
                timeline_out_seconds=2,
                role="build",
                target_energy=.5,
                shot_energy=.5,
                confidence=.9,
                reason="fixture",
            ),
            EditSegment(
                id="right",
                asset_id="right-asset",
                shot_id="right-shot",
                source_in_seconds=.5,
                source_out_seconds=2.5,
                timeline_in_seconds=2,
                timeline_out_seconds=4,
                role="reveal",
                target_energy=.5,
                shot_energy=.5,
                confidence=.9,
                reason="fixture",
            ),
        ],
        strategy_notes=[],
    )
    critic = CriticReport(
        project_id="p",
        status="needs_revision",
        metrics=[],
        findings=[CriticFinding(
            code="action_cut_timing_shift_needed",
            severity="warning",
            boundary_index=1,
            suggested_shift_seconds=.25,
            message="verified dense-flow timing shift",
        )],
        notes=[],
    )

    revised, report = revise_edit_plan(edit, vir, critic)

    assert report.changed is True
    action = next(item for item in report.actions if item.kind == "roll_boundary")
    assert action.boundary_index == 1
    assert action.boundary_shift_seconds == .25
    assert action.verification_kind == "advanced_action_timing"
    assert revised.segments[0].timeline_out_seconds == 2.25
    assert revised.segments[1].timeline_in_seconds == 2.25
