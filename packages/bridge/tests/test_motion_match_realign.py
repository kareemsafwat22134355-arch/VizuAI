import pytest

from monter_bridge.analysis_models import EditAnchor, GlobalMotionSummary, ShotAnalysis, TimeRange, VirProject
from monter_bridge.critic import critique_edit
from monter_bridge.critic_models import CriticFinding, CriticReport
from monter_bridge.ctl import compile_ctl
from monter_bridge.ctl_models import CtlClip, CtlProgram, CtlTransition, TimeWarpIntent, TimeWarpSlice
from monter_bridge.cut_signature import build_cut_signature
from monter_bridge.motion_match_realign import apply_motion_match_realign, propose_motion_match_realign
from monter_bridge.planning_models import EditPlan, EditSegment
from monter_bridge.revision import revise_edit_plan


def fixture_edit_and_vir():
    motion = GlobalMotionSummary(
        dominant_screen_direction="right",
        zoom_direction="static",
        confidence=.9,
    )
    left_shot = ShotAnalysis(
        id="left_shot",
        asset_id="left_asset",
        range=TimeRange(start_seconds=0, end_seconds=3),
        mean_motion=1,
        peak_motion=2,
        motion_samples=[],
        edit_anchors=[
            EditAnchor(type="motion_peak", time_seconds=1.92, confidence=.92, reason="outgoing peak"),
        ],
        global_motion=motion,
    )
    right_shot = ShotAnalysis(
        id="right_shot",
        asset_id="right_asset",
        range=TimeRange(start_seconds=0, end_seconds=3),
        mean_motion=1,
        peak_motion=2,
        motion_samples=[],
        edit_anchors=[
            EditAnchor(type="motion_onset", time_seconds=.58, confidence=.90, reason="incoming onset"),
        ],
        global_motion=motion,
    )
    edit = EditPlan(
        project_id="p",
        target_duration_seconds=2,
        actual_duration_seconds=2,
        segments=[
            EditSegment(
                id="left", asset_id="left_asset", shot_id="left_shot",
                source_in_seconds=.5, source_out_seconds=1.5,
                timeline_in_seconds=0, timeline_out_seconds=1,
                role="build", target_energy=.5, shot_energy=.5, confidence=.9, reason="fixture",
            ),
            EditSegment(
                id="right", asset_id="right_asset", shot_id="right_shot",
                source_in_seconds=1.0, source_out_seconds=2.0,
                timeline_in_seconds=1, timeline_out_seconds=2,
                role="build", target_energy=.5, shot_energy=.5, confidence=.9, reason="fixture",
            ),
        ],
        strategy_notes=[],
    )
    return edit, VirProject.new("p", [left_shot, right_shot]), left_shot, right_shot


def fixture_ctl(edit: EditPlan, mechanism="motion_match_cut", with_timewarp=False):
    ctl = CtlProgram(
        project_id="p",
        duration_seconds=2,
        clips=[
            CtlClip(
                id=segment.id,
                asset_id=segment.asset_id,
                shot_id=segment.shot_id,
                source_in_seconds=segment.source_in_seconds,
                source_out_seconds=segment.source_out_seconds,
                timeline_in_seconds=segment.timeline_in_seconds,
                timeline_out_seconds=segment.timeline_out_seconds,
            )
            for segment in edit.segments
        ],
        transitions=[CtlTransition(boundary_index=1, mechanism=mechanism, reason="fixture")],
        render_fps=24,
        render_width=960,
    )
    if with_timewarp:
        ctl.time_warps = [TimeWarpIntent(
            segment_id="left",
            anchor_seconds=1,
            reason="fixture warp",
            slices=[
                TimeWarpSlice(source_in_seconds=.5, source_out_seconds=1.0, playback_rate=.8),
                TimeWarpSlice(source_in_seconds=1.0, source_out_seconds=1.5, playback_rate=1.2),
            ],
        )]
    return ctl


def test_proposal_shifts_source_windows_to_action_grade_phase_without_moving_timeline():
    edit, vir, left_shot, right_shot = fixture_edit_and_vir()
    before = build_cut_signature(edit.segments[0], edit.segments[1], left_shot, right_shot)
    proposal = propose_motion_match_realign(edit, vir, 1)

    assert proposal is not None
    assert before.phase_compatibility == pytest.approx(.15)
    assert proposal.left_shift_seconds == pytest.approx(.42)
    assert proposal.right_shift_seconds == pytest.approx(-.42)
    assert proposal.after_phase_compatibility == pytest.approx(1.0)

    original_timeline = [
        (segment.timeline_in_seconds, segment.timeline_out_seconds)
        for segment in edit.segments
    ]
    original_source_durations = [
        segment.source_out_seconds - segment.source_in_seconds
        for segment in edit.segments
    ]
    apply_motion_match_realign(edit, proposal)

    assert [
        (segment.timeline_in_seconds, segment.timeline_out_seconds)
        for segment in edit.segments
    ] == original_timeline
    assert [
        segment.source_out_seconds - segment.source_in_seconds
        for segment in edit.segments
    ] == pytest.approx(original_source_durations)
    after = build_cut_signature(edit.segments[0], edit.segments[1], left_shot, right_shot)
    assert after.phase_compatibility == pytest.approx(1.0)


def test_critic_emits_recoverable_timing_only_for_motion_match_cut():
    edit, vir, _, _ = fixture_edit_and_vir()
    report = critique_edit(edit, fixture_ctl(edit, "motion_match_cut"), vir)

    finding = next(item for item in report.findings if item.code == "motion_match_timing_weak")
    metric = next(item for item in report.metrics if item.name == "recoverable_motion_match_timing_count")
    assert finding.boundary_index == 1
    assert metric.value == 1
    assert metric.passed is False
    assert report.status == "needs_revision"

    hard_cut_report = critique_edit(edit, fixture_ctl(edit, "hard_cut"), vir)
    assert not any(item.code == "motion_match_timing_weak" for item in hard_cut_report.findings)
    hard_metric = next(item for item in hard_cut_report.metrics if item.name == "recoverable_motion_match_timing_count")
    assert hard_metric.value == 0


def test_timewarp_adjacent_boundary_is_not_realigned():
    edit, vir, _, _ = fixture_edit_and_vir()
    report = critique_edit(edit, fixture_ctl(edit, "motion_match_cut", with_timewarp=True), vir)

    assert not any(item.code == "motion_match_timing_weak" for item in report.findings)


def test_revision_applies_boundary_realign_and_records_machine_readable_shifts():
    edit, vir, left_shot, right_shot = fixture_edit_and_vir()
    report = CriticReport(
        project_id="p",
        status="needs_revision",
        metrics=[],
        findings=[CriticFinding(
            code="motion_match_timing_weak",
            severity="warning",
            boundary_index=1,
            message="recoverable timing",
        )],
        notes=[],
    )

    revised, revision = revise_edit_plan(edit, vir, report)

    assert revision.changed is True
    action = next(action for action in revision.actions if action.kind == "realign_boundary")
    assert action.boundary_index == 1
    assert action.left_shift_seconds == pytest.approx(.42)
    assert action.right_shift_seconds == pytest.approx(-.42)
    assert revised.actual_duration_seconds == edit.actual_duration_seconds
    assert revised.segments[0].timeline_out_seconds == edit.segments[0].timeline_out_seconds
    assert revised.segments[1].timeline_in_seconds == edit.segments[1].timeline_in_seconds
    after = build_cut_signature(revised.segments[0], revised.segments[1], left_shot, right_shot)
    assert after.phase_compatibility == pytest.approx(1.0)


def test_realign_revision_recompiles_without_the_recoverable_timing_finding():
    edit, vir, _, _ = fixture_edit_and_vir()
    baseline = critique_edit(edit, fixture_ctl(edit, "motion_match_cut"), vir)
    revised, revision = revise_edit_plan(edit, vir, baseline)

    assert any(action.kind == "realign_boundary" for action in revision.actions)
    revised_ctl = compile_ctl(revised, vir, fps=24, width=960)
    revised_critic = critique_edit(revised, revised_ctl, vir)

    assert not any(item.code == "motion_match_timing_weak" for item in revised_critic.findings)
    timing_metric = next(item for item in revised_critic.metrics if item.name == "recoverable_motion_match_timing_count")
    assert timing_metric.value == 0
    assert timing_metric.passed is True
    assert revised_critic.status == "pass"


def test_realign_is_skipped_when_adjacent_segment_is_replaced_in_same_pass():
    edit, vir, _, _ = fixture_edit_and_vir()
    vir.shots.append(ShotAnalysis(
        id="replacement",
        asset_id="replacement_asset",
        range=TimeRange(start_seconds=0, end_seconds=3),
        mean_motion=2,
        peak_motion=2,
        motion_samples=[],
        edit_anchors=[],
    ))
    report = CriticReport(
        project_id="p",
        status="needs_revision",
        metrics=[],
        findings=[
            CriticFinding(code="motion_match_timing_weak", severity="warning", boundary_index=1, message="timing"),
            CriticFinding(code="low_confidence_selection", severity="warning", segment_id="left", message="replace"),
        ],
        notes=[],
    )

    _, revision = revise_edit_plan(edit, vir, report)
    assert any(action.kind == "replace_segment" and action.segment_id == "left" for action in revision.actions)
    assert not any(action.kind == "realign_boundary" for action in revision.actions)
