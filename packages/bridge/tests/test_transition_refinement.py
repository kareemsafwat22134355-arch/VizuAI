from monter_bridge.advanced_execution_models import (
    AdvancedAnalysisResults,
    BoundaryExecutionResult,
    DenseFlowWindowSummary,
    FeatureExecutionResult,
)
from monter_bridge.analysis_models import GlobalMotionSummary, ShotAnalysis, TimeRange, VirProject
from monter_bridge.ctl import compile_ctl
from monter_bridge.planning_models import EditPlan, EditSegment
from monter_bridge.transition_opportunities import synthesize_transition_opportunities
from monter_bridge.transition_refinement import refine_transition_opportunities
from monter_bridge.transition_refinement_models import BoundaryTransitionRefinement, TransitionRefinementReport


def directional_fixture():
    motion = GlobalMotionSummary(dominant_screen_direction="right", zoom_direction="static", confidence=.9)
    shot_a = ShotAnalysis(id="a", asset_id="a", range=TimeRange(start_seconds=0, end_seconds=3), mean_motion=1, peak_motion=1, motion_samples=[], edit_anchors=[], global_motion=motion)
    shot_b = ShotAnalysis(id="b", asset_id="b", range=TimeRange(start_seconds=3, end_seconds=6), mean_motion=1, peak_motion=1, motion_samples=[], edit_anchors=[], global_motion=motion)
    edit = EditPlan(
        project_id="p", target_duration_seconds=4, actual_duration_seconds=4,
        segments=[
            EditSegment(id="s1", asset_id="a", shot_id="a", source_in_seconds=.4, source_out_seconds=2.6, timeline_in_seconds=0, timeline_out_seconds=2, role="build", target_energy=.5, shot_energy=.6, confidence=.9, reason="x"),
            EditSegment(id="s2", asset_id="b", shot_id="b", source_in_seconds=3.4, source_out_seconds=5.6, timeline_in_seconds=2, timeline_out_seconds=4, role="reveal", target_energy=.5, shot_energy=.4, confidence=.8, reason="y"),
        ],
    )
    vir = VirProject.new("p", [shot_a, shot_b])
    return edit, vir


def flow_summary(segment_id: str, asset_id: str, shot_id: str, dx: float, coherence: float = .7):
    return DenseFlowWindowSummary(
        segment_id=segment_id,
        asset_id=asset_id,
        shot_id=shot_id,
        source_start_seconds=.5,
        source_end_seconds=1.5,
        sample_count=6,
        mean_magnitude=1.2,
        p90_magnitude=2.0,
        mean_dx=dx,
        mean_dy=0,
        directional_coherence=coherence,
    )


def results(compatibility: float, *, left_coherence=.7, right_coherence=.7, status="completed"):
    return AdvancedAnalysisResults(
        project_id="p",
        boundaries=[
            BoundaryExecutionResult(
                boundary_index=1,
                priority=.8,
                left_flow=flow_summary("s1", "a", "a", 1.0, left_coherence),
                right_flow=flow_summary("s2", "b", "b", 1.0 if compatibility >= .5 else -1.0, right_coherence),
                flow_direction_compatibility=compatibility,
                features=[
                    FeatureExecutionResult(
                        feature="dense_flow",
                        status=status,
                        backend="opencv-farneback",
                        reason="fixture",
                    )
                ],
            )
        ],
    )


def test_dense_flow_confirms_directional_bridge():
    edit, vir = directional_fixture()
    opportunities = synthesize_transition_opportunities(edit, vir)
    refinement = refine_transition_opportunities(opportunities, results(.91))

    assert refinement.boundaries[0].status == "confirmed"
    assert refinement.boundaries[0].refined_mechanism == "directional_bridge"

    ctl = compile_ctl(edit, vir, transition_refinement=refinement)
    assert ctl.transitions[0].mechanism == "directional_bridge"
    assert ctl.transitions[0].evidence["advancedRefinementStatus"] == "confirmed"


def test_dense_flow_can_demote_directional_bridge_to_hard_cut():
    edit, vir = directional_fixture()
    opportunities = synthesize_transition_opportunities(edit, vir)
    refinement = refine_transition_opportunities(opportunities, results(.12))

    assert refinement.boundaries[0].status == "demoted"
    assert refinement.boundaries[0].refined_mechanism == "hard_cut"

    ctl = compile_ctl(edit, vir, transition_refinement=refinement)
    assert ctl.transitions[0].mechanism == "hard_cut"
    assert ctl.transitions[0].duration_seconds == 0
    assert ctl.transitions[0].evidence["advancedFlowDirectionCompatibility"] == .12


def test_low_coherence_flow_does_not_overrule_base_recommendation():
    edit, vir = directional_fixture()
    opportunities = synthesize_transition_opportunities(edit, vir)
    refinement = refine_transition_opportunities(opportunities, results(.10, left_coherence=.05, right_coherence=.08))

    assert refinement.boundaries[0].status == "unresolved"
    assert refinement.boundaries[0].refined_mechanism == "directional_bridge"


def test_failed_dense_flow_does_not_overrule_base_recommendation():
    edit, vir = directional_fixture()
    opportunities = synthesize_transition_opportunities(edit, vir)
    refinement = refine_transition_opportunities(opportunities, results(.10, status="failed"))

    assert refinement.boundaries[0].status == "unresolved"
    assert refinement.boundaries[0].refined_mechanism == "directional_bridge"


def test_compile_rejects_stale_refinement_base():
    edit, vir = directional_fixture()
    stale = TransitionRefinementReport(
        project_id="p",
        boundaries=[
            BoundaryTransitionRefinement(
                boundary_index=1,
                base_mechanism="hard_cut",
                refined_mechanism="hard_cut",
                status="unchanged",
                reason="stale fixture",
            )
        ],
    )
    try:
        compile_ctl(edit, vir, transition_refinement=stale)
    except ValueError as exc:
        assert "stale" in str(exc)
    else:
        raise AssertionError("expected stale refinement guard")


def test_refinement_rejects_cross_project_results():
    edit, vir = directional_fixture()
    opportunities = synthesize_transition_opportunities(edit, vir)
    other = results(.9)
    other.project_id = "other"
    try:
        refine_transition_opportunities(opportunities, other)
    except ValueError as exc:
        assert "projectId" in str(exc)
    else:
        raise AssertionError("expected project identity guard")
