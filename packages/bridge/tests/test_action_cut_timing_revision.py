import pytest

from monter_bridge.analysis_models import EditAnchor, GlobalMotionSummary, ShotAnalysis, TimeRange, VirProject
from monter_bridge.critic import critique_edit
from monter_bridge.critic_models import CriticFinding, CriticReport
from monter_bridge.ctl_models import CtlClip, CtlProgram, CtlTransition, TimeWarpIntent, TimeWarpSlice
from monter_bridge.final_critic import build_final_critic
from monter_bridge.planning_models import EditPlan, EditSegment
from monter_bridge.post_render_revision import filter_automatic_editorial_critic
from monter_bridge.revision import revise_edit_plan


def fixture_edit_and_vir(*, left_source_out=1.8):
    motion = GlobalMotionSummary(dominant_screen_direction="static", zoom_direction="static", confidence=.9)
    left_shot = ShotAnalysis(
        id="left_shot", asset_id="left_asset",
        range=TimeRange(start_seconds=0, end_seconds=4),
        mean_motion=1, peak_motion=2, motion_samples=[],
        edit_anchors=[EditAnchor(
            type="motion_peak",
            time_seconds=max(.01, left_source_out - .05),
            confidence=.92,
            reason="cheap action evidence remains near the rolled boundary",
        )],
        global_motion=motion,
    )
    right_shot = ShotAnalysis(
        id="right_shot", asset_id="right_asset",
        range=TimeRange(start_seconds=0, end_seconds=4),
        mean_motion=1, peak_motion=2, motion_samples=[], edit_anchors=[], global_motion=motion,
    )
    edit = EditPlan(
        project_id="p", target_duration_seconds=4, actual_duration_seconds=4,
        segments=[
            EditSegment(
                id="left", asset_id="left_asset", shot_id="left_shot",
                source_in_seconds=.2, source_out_seconds=left_source_out,
                timeline_in_seconds=0, timeline_out_seconds=2,
                role="build", target_energy=.5, shot_energy=.5, confidence=.9, reason="fixture",
            ),
            EditSegment(
                id="right", asset_id="right_asset", shot_id="right_shot",
                source_in_seconds=.5, source_out_seconds=2.5,
                timeline_in_seconds=2, timeline_out_seconds=4,
                role="reveal", target_energy=.5, shot_energy=.5, confidence=.9, reason="fixture",
            ),
        ],
        strategy_notes=[],
    )
    return edit, VirProject.new("p", [left_shot, right_shot])


def advanced_ctl(edit: EditPlan, *, shift=.25, with_timewarp=False, status="unchanged"):
    ctl = CtlProgram(
        project_id="p",
        duration_seconds=4,
        clips=[
            CtlClip(
                id=segment.id, asset_id=segment.asset_id, shot_id=segment.shot_id,
                source_in_seconds=segment.source_in_seconds, source_out_seconds=segment.source_out_seconds,
                timeline_in_seconds=segment.timeline_in_seconds, timeline_out_seconds=segment.timeline_out_seconds,
            )
            for segment in edit.segments
        ],
        transitions=[CtlTransition(
            boundary_index=1,
            mechanism="motion_peak_cut",
            reason="advanced action fixture",
            evidence={
                "advancedRefinementStatus": status,
                "advancedBaseMechanism": "action_cut",
                "advancedRefinedMechanism": "action_cut",
                "advancedSuggestedBoundaryShiftSeconds": shift,
                "advancedActionOffsetDisagreementSeconds": .03,
                "adjacentTimewarp": with_timewarp,
            },
        )],
        render_fps=24,
        render_width=960,
    )
    if with_timewarp:
        ctl.time_warps = [TimeWarpIntent(
            segment_id="left",
            anchor_seconds=1.0,
            reason="fixture warp",
            slices=[
                TimeWarpSlice(source_in_seconds=.2, source_out_seconds=1.0, playback_rate=.8),
                TimeWarpSlice(source_in_seconds=1.0, source_out_seconds=1.8, playback_rate=1.2),
            ],
        )]
    return ctl


def test_critic_turns_reliable_advanced_shift_into_typed_revision_finding():
    edit, vir = fixture_edit_and_vir()
    report = critique_edit(edit, advanced_ctl(edit, shift=.25), vir)

    finding = next(item for item in report.findings if item.code == "action_cut_timing_shift_needed")
    metric = next(item for item in report.metrics if item.name == "recoverable_advanced_action_timing_count")
    assert report.status == "needs_revision"
    assert finding.boundary_index == 1
    assert finding.suggested_shift_seconds == pytest.approx(.25)
    assert metric.value == 1
    assert metric.passed is False


def test_critic_does_not_authorize_advanced_roll_when_timewarp_owns_boundary():
    edit, vir = fixture_edit_and_vir()
    report = critique_edit(edit, advanced_ctl(edit, shift=.25, with_timewarp=True), vir)

    assert not any(item.code == "action_cut_timing_shift_needed" for item in report.findings)
    metric = next(item for item in report.metrics if item.name == "recoverable_advanced_action_timing_count")
    assert metric.value == 0


def test_critic_rechecks_source_bounds_before_authorizing_advanced_roll():
    edit, vir = fixture_edit_and_vir(left_source_out=3.9)
    report = critique_edit(edit, advanced_ctl(edit, shift=.25), vir)

    assert not any(item.code == "action_cut_timing_shift_needed" for item in report.findings)


def test_revision_applies_exact_typed_dense_flow_shift_and_preserves_total_duration():
    edit, vir = fixture_edit_and_vir()
    report = CriticReport(
        project_id="p",
        status="needs_revision",
        metrics=[],
        findings=[CriticFinding(
            code="action_cut_timing_shift_needed",
            severity="warning",
            boundary_index=1,
            suggested_shift_seconds=.25,
            message="dense flow supports +.25s",
        )],
        notes=[],
    )

    revised, revision = revise_edit_plan(edit, vir, report)

    assert revision.changed is True
    action = next(item for item in revision.actions if item.kind == "roll_boundary")
    assert action.boundary_index == 1
    assert action.boundary_shift_seconds == pytest.approx(.25)
    assert revised.actual_duration_seconds == edit.actual_duration_seconds == 4
    assert revised.segments[0].timeline_in_seconds == 0
    assert revised.segments[-1].timeline_out_seconds == 4
    assert revised.segments[0].timeline_out_seconds == pytest.approx(2.25)
    assert revised.segments[1].timeline_in_seconds == pytest.approx(2.25)
    assert revised.segments[0].source_out_seconds == pytest.approx(2.05)
    assert revised.segments[1].source_in_seconds == pytest.approx(.75)


def test_revision_revalidates_shift_instead_of_trusting_finding_blindly():
    edit, vir = fixture_edit_and_vir(left_source_out=3.9)
    report = CriticReport(
        project_id="p", status="needs_revision", metrics=[],
        findings=[CriticFinding(
            code="action_cut_timing_shift_needed", severity="warning",
            boundary_index=1, suggested_shift_seconds=.25, message="stale shift",
        )], notes=[],
    )

    revised, revision = revise_edit_plan(edit, vir, report)
    assert revision.changed is False
    assert not any(item.kind == "roll_boundary" for item in revision.actions)
    assert revised.segments[0].timeline_out_seconds == 2


def test_final_critic_and_post_render_filter_preserve_typed_shift_authorization():
    edit, vir = fixture_edit_and_vir()
    editorial = critique_edit(edit, advanced_ctl(edit, shift=.25), vir)
    final = build_final_critic(editorial)

    final_finding = next(item for item in final.findings if item.code == "action_cut_timing_shift_needed")
    assert final.status == "needs_revision"
    assert final_finding.reviseability == "automatic_candidate"
    assert final_finding.boundary_index == 1
    assert final_finding.suggested_shift_seconds == pytest.approx(.25)

    filtered = filter_automatic_editorial_critic(editorial, final)
    filtered_finding = next(item for item in filtered.findings if item.code == "action_cut_timing_shift_needed")
    assert filtered_finding.boundary_index == 1
    assert filtered_finding.suggested_shift_seconds == pytest.approx(.25)


def test_replacement_conflict_skips_advanced_timing_roll():
    edit, vir = fixture_edit_and_vir()
    vir.shots.append(ShotAnalysis(
        id="replacement", asset_id="replacement_asset",
        range=TimeRange(start_seconds=0, end_seconds=4),
        mean_motion=1, peak_motion=1, motion_samples=[], edit_anchors=[],
    ))
    edit.segments[0].confidence = .2
    report = CriticReport(
        project_id="p", status="needs_revision", metrics=[],
        findings=[
            CriticFinding(
                code="action_cut_timing_shift_needed", severity="warning",
                boundary_index=1, suggested_shift_seconds=.25, message="timing",
            ),
            CriticFinding(
                code="low_confidence_selection", severity="warning",
                segment_id="left", message="replace",
            ),
        ], notes=[],
    )

    _, revision = revise_edit_plan(edit, vir, report)
    assert any(item.kind == "replace_segment" and item.segment_id == "left" for item in revision.actions)
    assert not any(item.kind == "roll_boundary" for item in revision.actions)
