from monter_bridge.advanced_analysis import build_advanced_analysis_plan
from monter_bridge.ctl_models import CtlClip, CtlProgram, CtlTransition
from monter_bridge.cut_signature import CutSignature
from monter_bridge.transition_opportunities import (
    BoundaryTransitionOpportunity,
    TransitionCandidate,
    TransitionOpportunityReport,
)


def ctl(adjacent_timewarp: bool = False) -> CtlProgram:
    return CtlProgram(
        project_id="p",
        duration_seconds=4,
        clips=[
            CtlClip(id="s1", asset_id="a", shot_id="sa", source_in_seconds=.5, source_out_seconds=2.5, timeline_in_seconds=0, timeline_out_seconds=2),
            CtlClip(id="s2", asset_id="b", shot_id="sb", source_in_seconds=1.0, source_out_seconds=3.0, timeline_in_seconds=2, timeline_out_seconds=4),
        ],
        transitions=[
            CtlTransition(
                boundary_index=1,
                mechanism="motion_match_cut",
                evidence={"adjacentTimewarp": adjacent_timewarp},
                reason="fixture",
            )
        ],
        render_fps=24,
        render_width=960,
    )


def report(mechanism: str, *, relation=.65, direction=.9, zoom=.7, phase=.15, confidence=.5, feasible=True):
    candidate = TransitionCandidate(
        mechanism=mechanism,
        duration_seconds=.14 if mechanism == "zoom_bridge" else (.12 if mechanism == "directional_bridge" else 0),
        required_handle_seconds=.1 if mechanism == "zoom_bridge" else (.08 if mechanism == "directional_bridge" else 0),
        feasible=feasible,
        feasibility_score=1.0 if feasible else 0.0,
        motivation_score=.8,
        relation_score=relation,
        parameters={},
        reason="fixture",
    )
    boundary = BoundaryTransitionOpportunity(
        boundary_index=1,
        left_segment_id="s1",
        right_segment_id="s2",
        outgoing_handle_seconds=.25,
        incoming_handle_seconds=.25,
        cut_signature=CutSignature(
            direction_compatibility=direction,
            zoom_compatibility=zoom,
            phase_compatibility=phase,
            global_motion_confidence=confidence,
            relation_score=relation,
        ),
        recommended_mechanism=mechanism,
        candidates=[candidate],
    )
    return TransitionOpportunityReport(project_id="p", boundaries=[boundary])


def test_feasible_zoom_bridge_schedules_dense_flow_and_depth():
    plan = build_advanced_analysis_plan(ctl(), report("zoom_bridge", zoom=1.0, confidence=.7))
    assert len(plan.requests) == 1
    assert plan.requests[0].requested_features == ["dense_flow", "depth"]
    assert plan.requests[0].left_window.source_end_seconds > 2.5
    assert plan.requests[0].right_window.source_start_seconds < 1.0


def test_analysis_windows_stay_inside_selected_source_or_verified_handles():
    program = ctl()
    program.clips[0].source_in_seconds = 2.3
    plan = build_advanced_analysis_plan(program, report("zoom_bridge", zoom=1.0, confidence=.7))
    request = plan.requests[0]
    assert request.left_window.source_start_seconds == 2.3
    assert request.left_window.source_end_seconds <= 2.75
    assert request.right_window.source_start_seconds == 0.75
    assert request.right_window.source_end_seconds <= program.clips[1].source_out_seconds


def test_strong_directional_bridge_stays_cheap():
    plan = build_advanced_analysis_plan(ctl(), report("directional_bridge", relation=.82, direction=1.0, confidence=.8))
    assert plan.requests == []
    assert "no expensive" in plan.skipped_boundaries[0].reason.lower()


def test_borderline_directional_bridge_gets_dense_flow_only():
    plan = build_advanced_analysis_plan(ctl(), report("directional_bridge", relation=.61, direction=1.0, confidence=.45))
    assert len(plan.requests) == 1
    assert plan.requests[0].requested_features == ["dense_flow"]


def test_ambiguous_action_cut_gets_dense_flow_refinement():
    plan = build_advanced_analysis_plan(ctl(), report("action_cut", phase=.65, relation=.45, direction=.3, confidence=.4))
    assert plan.requests[0].requested_features == ["dense_flow"]


def test_strong_action_cut_is_forced_back_into_dense_flow_for_revision_verification():
    strong = report("action_cut", phase=.95, relation=.7, direction=.3, confidence=.8)
    normal = build_advanced_analysis_plan(ctl(), strong)
    assert normal.requests == []

    forced = build_advanced_analysis_plan(
        ctl(),
        strong,
        max_boundaries=1,
        forced_action_boundaries={1},
    )
    assert len(forced.requests) == 1
    request = forced.requests[0]
    assert request.boundary_index == 1
    assert request.requested_features == ["dense_flow"]
    assert request.priority == 1.0
    assert request.evidence["forcedRevisionVerification"] is True
    assert "mandatory" in request.reason.lower()


def test_adjacent_timewarp_blocks_extra_transition_analysis_even_when_forced():
    plan = build_advanced_analysis_plan(
        ctl(adjacent_timewarp=True),
        report("action_cut", phase=.95, relation=.7, direction=.3, confidence=.8),
        forced_action_boundaries={1},
    )
    assert plan.requests == []
    assert "timewarp" in plan.skipped_boundaries[0].reason.lower()


def test_project_identity_must_match():
    opportunities = report("zoom_bridge")
    opportunities.project_id = "other"
    try:
        build_advanced_analysis_plan(ctl(), opportunities)
    except ValueError as exc:
        assert "projectId" in str(exc)
    else:
        raise AssertionError("expected project identity guard")
