import pytest

from monter_bridge.analysis_models import EditAnchor, GlobalMotionSummary, ShotAnalysis, TimeRange, VirProject
from monter_bridge.critic import critique_edit
from monter_bridge.critic_models import CriticFinding, CriticReport
from monter_bridge.ctl import compile_ctl
from monter_bridge.ctl_models import CtlClip, CtlProgram, CtlTransition, TimeWarpIntent, TimeWarpSlice
from monter_bridge.final_critic import build_final_critic
from monter_bridge.motion_match_realign import propose_motion_match_realign
from monter_bridge.motion_match_roll import apply_motion_match_boundary_roll, propose_motion_match_boundary_roll
from monter_bridge.planning_models import EditPlan, EditSegment
from monter_bridge.post_render_revision import filter_automatic_editorial_critic
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
        range=TimeRange(start_seconds=0, end_seconds=2.5),
        mean_motion=1,
        peak_motion=2,
        motion_samples=[],
        edit_anchors=[
            EditAnchor(type="motion_peak", time_seconds=1.82, confidence=.92, reason="outgoing peak"),
        ],
        global_motion=motion,
    )
    right_shot = ShotAnalysis(
        id="right_shot",
        asset_id="right_asset",
        range=TimeRange(start_seconds=0, end_seconds=2.0),
        mean_motion=1,
        peak_motion=2,
        motion_samples=[],
        edit_anchors=[
            EditAnchor(type="motion_onset", time_seconds=1.22, confidence=.91, reason="incoming onset"),
        ],
        global_motion=motion,
    )
    edit = EditPlan(
        project_id="p",
        target_duration_seconds=2.4,
        actual_duration_seconds=2.4,
        segments=[
            EditSegment(
                id="left", asset_id="left_asset", shot_id="left_shot",
                source_in_seconds=.2, source_out_seconds=1.4,
                timeline_in_seconds=0, timeline_out_seconds=1.2,
                role="build", target_energy=.5, shot_energy=.5, confidence=.9, reason="fixture",
            ),
            EditSegment(
                id="right", asset_id="right_asset", shot_id="right_shot",
                source_in_seconds=.8, source_out_seconds=2.0,
                timeline_in_seconds=1.2, timeline_out_seconds=2.4,
                role="build", target_energy=.5, shot_energy=.5, confidence=.9, reason="fixture",
            ),
        ],
        strategy_notes=[],
    )
    return edit, VirProject.new("p", [left_shot, right_shot])


def fixture_ctl(edit: EditPlan, mechanism="motion_match_cut", with_timewarp=False):
    ctl = CtlProgram(
        project_id="p",
        duration_seconds=2.4,
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
            segment_id="right",
            anchor_seconds=1.5,
            reason="fixture warp",
            slices=[
                TimeWarpSlice(source_in_seconds=.8, source_out_seconds=1.4, playback_rate=.8),
                TimeWarpSlice(source_in_seconds=1.4, source_out_seconds=2.0, playback_rate=1.2),
            ],
        )]
    return ctl


def test_roll_is_fallback_when_slip_cannot_fit_in_source_handles():
    edit, vir = fixture_edit_and_vir()

    assert propose_motion_match_realign(edit, vir, 1) is None
    proposal = propose_motion_match_boundary_roll(edit, vir, 1)

    assert proposal is not None
    assert proposal.boundary_shift_seconds == pytest.approx(.42)
    assert proposal.before_phase_compatibility == pytest.approx(.15)
    assert proposal.after_phase_compatibility == pytest.approx(1.0)


def test_roll_moves_shared_boundary_but_preserves_sequence_start_end_and_total_duration():
    edit, vir = fixture_edit_and_vir()
    proposal = propose_motion_match_boundary_roll(edit, vir, 1)
    assert proposal is not None

    sequence_start = edit.segments[0].timeline_in_seconds
    sequence_end = edit.segments[-1].timeline_out_seconds
    total = edit.actual_duration_seconds
    apply_motion_match_boundary_roll(edit, proposal)

    assert edit.segments[0].timeline_in_seconds == sequence_start
    assert edit.segments[-1].timeline_out_seconds == sequence_end
    assert edit.actual_duration_seconds == total
    assert edit.segments[0].timeline_out_seconds == pytest.approx(1.62)
    assert edit.segments[1].timeline_in_seconds == pytest.approx(1.62)
    assert edit.segments[0].source_out_seconds == pytest.approx(1.82)
    assert edit.segments[1].source_in_seconds == pytest.approx(1.22)
    assert edit.segments[0].timeline_out_seconds - edit.segments[0].timeline_in_seconds == pytest.approx(1.62)
    assert edit.segments[1].timeline_out_seconds - edit.segments[1].timeline_in_seconds == pytest.approx(.78)


def test_critic_uses_roll_only_for_motion_match_and_not_timewarp_or_hard_cut():
    edit, vir = fixture_edit_and_vir()
    report = critique_edit(edit, fixture_ctl(edit), vir)

    finding = next(item for item in report.findings if item.code == "motion_match_boundary_roll_needed")
    metric = next(item for item in report.metrics if item.name == "recoverable_motion_match_roll_count")
    assert finding.boundary_index == 1
    assert metric.value == 1
    assert report.status == "needs_revision"
    assert not any(item.code == "motion_match_timing_weak" for item in report.findings)

    hard_cut = critique_edit(edit, fixture_ctl(edit, mechanism="hard_cut"), vir)
    assert not any(item.code == "motion_match_boundary_roll_needed" for item in hard_cut.findings)

    warped = critique_edit(edit, fixture_ctl(edit, with_timewarp=True), vir)
    assert not any(item.code == "motion_match_boundary_roll_needed" for item in warped.findings)


def test_revision_rolls_boundary_and_recompiled_critic_clears_finding():
    edit, vir = fixture_edit_and_vir()
    baseline = critique_edit(edit, fixture_ctl(edit), vir)
    revised, revision = revise_edit_plan(edit, vir, baseline)

    action = next(action for action in revision.actions if action.kind == "roll_boundary")
    assert action.boundary_index == 1
    assert action.boundary_shift_seconds == pytest.approx(.42)
    assert revision.changed is True

    revised_ctl = compile_ctl(revised, vir, fps=24, width=960)
    revised_critic = critique_edit(revised, revised_ctl, vir)
    assert not any(item.code == "motion_match_boundary_roll_needed" for item in revised_critic.findings)
    assert not any(item.code == "motion_match_timing_weak" for item in revised_critic.findings)
    assert revised_critic.status == "pass"


def test_roll_finding_is_explicitly_whitelisted_through_final_and_post_render_critics():
    edit, vir = fixture_edit_and_vir()
    editorial = critique_edit(edit, fixture_ctl(edit), vir)
    final = build_final_critic(editorial)

    consolidated = next(item for item in final.findings if item.code == "motion_match_boundary_roll_needed")
    assert consolidated.reviseability == "automatic_candidate"
    assert consolidated.boundary_index == 1

    filtered = filter_automatic_editorial_critic(editorial, final)
    assert any(
        item.code == "motion_match_boundary_roll_needed" and item.boundary_index == 1
        for item in filtered.findings
    )


def test_roll_is_skipped_when_adjacent_segment_is_scheduled_for_replacement():
    edit, vir = fixture_edit_and_vir()
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
            CriticFinding(code="motion_match_boundary_roll_needed", severity="warning", boundary_index=1, message="roll"),
            CriticFinding(code="low_confidence_selection", severity="warning", segment_id="right", message="replace"),
        ],
        notes=[],
    )

    _, revision = revise_edit_plan(edit, vir, report)
    assert any(action.kind == "replace_segment" and action.segment_id == "right" for action in revision.actions)
    assert not any(action.kind == "roll_boundary" for action in revision.actions)
