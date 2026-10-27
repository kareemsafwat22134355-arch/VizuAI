from monter_bridge.advanced_analysis import build_advanced_analysis_plan
from monter_bridge.ctl_models import CtlClip, CtlProgram, CtlTransition
from monter_bridge.cut_signature import CutSignature
from monter_bridge.transition_opportunities import (
    BoundaryTransitionOpportunity,
    TransitionCandidate,
    TransitionOpportunityReport,
)


def _ctl(adjacent_timewarp: bool = False) -> CtlProgram:
    return CtlProgram(
        project_id="p",
        duration_seconds=4,
        clips=[
            CtlClip(id="s1", asset_id="a", shot_id="sa", source_in_seconds=.4, source_out_seconds=2.0, timeline_in_seconds=0, timeline_out_seconds=2),
            CtlClip(id="s2", asset_id="b", shot_id="sb", source_in_seconds=1.0, source_out_seconds=2.8, timeline_in_seconds=2, timeline_out_seconds=4),
        ],
        transitions=[CtlTransition(
            boundary_index=1,
            mechanism="hard_cut",
            evidence={"adjacentTimewarp": adjacent_timewarp},
            reason="fixture",
        )],
        render_fps=24,
        render_width=960,
    )


def _report(
    mechanism: str = "hard_cut",
    *,
    occlusion_score: float = 0.0,
    occlusion_side: str = "none",
    occlusion_edge: str = "none",
    phase: float = .15,
    zoom: float = .7,
    confidence: float = .5,
) -> TransitionOpportunityReport:
    candidate = TransitionCandidate(
        mechanism=mechanism,
        duration_seconds=.14 if mechanism == "zoom_bridge" else 0.0,
        required_handle_seconds=.10 if mechanism == "zoom_bridge" else 0.0,
        feasible=True,
        feasibility_score=1.0,
        motivation_score=.8,
        relation_score=.65,
        parameters={},
        reason="fixture",
    )
    boundary = BoundaryTransitionOpportunity(
        boundary_index=1,
        left_segment_id="s1",
        right_segment_id="s2",
        outgoing_handle_seconds=.3,
        incoming_handle_seconds=.3,
        cut_signature=CutSignature(
            direction_compatibility=.4,
            zoom_compatibility=zoom,
            phase_compatibility=phase,
            global_motion_confidence=confidence,
            relation_score=.65,
        ),
        recommended_mechanism=mechanism,
        candidates=[candidate],
        occlusion_candidate_score=occlusion_score,
        occlusion_side=occlusion_side,
        occlusion_edge=occlusion_edge,
    )
    return TransitionOpportunityReport(project_id="p", boundaries=[boundary])


def test_strong_occlusion_can_schedule_segmentation_without_other_expensive_features():
    plan = build_advanced_analysis_plan(
        _ctl(),
        _report(occlusion_score=.82, occlusion_side="outgoing", occlusion_edge="left"),
    )

    assert len(plan.requests) == 1
    request = plan.requests[0]
    assert request.requested_features == ["segmentation"]
    assert request.evidence["occlusionCandidateScore"] == .82
    assert request.evidence["occlusionSide"] == "outgoing"
    assert request.evidence["occlusionEdge"] == "left"
    assert "segmentation" in request.reason.lower()


def test_subthreshold_occlusion_stays_cheap():
    plan = build_advanced_analysis_plan(
        _ctl(),
        _report(occlusion_score=.57, occlusion_side="outgoing", occlusion_edge="left"),
    )

    assert plan.requests == []


def test_occlusion_segmentation_is_merged_into_ambiguous_action_dense_flow_request():
    plan = build_advanced_analysis_plan(
        _ctl(),
        _report(
            mechanism="action_cut",
            phase=.65,
            occlusion_score=.74,
            occlusion_side="incoming",
            occlusion_edge="right",
        ),
    )

    assert len(plan.requests) == 1
    assert plan.requests[0].requested_features == ["dense_flow", "segmentation"]


def test_occlusion_segmentation_is_merged_into_zoom_analysis_request():
    plan = build_advanced_analysis_plan(
        _ctl(),
        _report(
            mechanism="zoom_bridge",
            zoom=1.0,
            confidence=.8,
            occlusion_score=.78,
            occlusion_side="both",
            occlusion_edge="mixed",
        ),
    )

    assert len(plan.requests) == 1
    assert plan.requests[0].requested_features == ["dense_flow", "depth", "segmentation"]


def test_timewarp_ownership_blocks_segmentation_even_with_strong_occlusion():
    plan = build_advanced_analysis_plan(
        _ctl(adjacent_timewarp=True),
        _report(occlusion_score=.9, occlusion_side="outgoing", occlusion_edge="left"),
    )

    assert plan.requests == []
    assert "timewarp" in plan.skipped_boundaries[0].reason.lower()
