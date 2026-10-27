from monter_bridge.analysis_models import (
    GlobalMotionSummary,
    OcclusionCueSample,
    OcclusionCueSummary,
    ShotAnalysis,
    TimeRange,
    VirProject,
)
from monter_bridge.planning_models import EditPlan, EditSegment
from monter_bridge.transition_opportunities import synthesize_transition_opportunities


def _shot(shot_id: str, asset_id: str, start: float, end: float, samples: list[OcclusionCueSample]) -> ShotAnalysis:
    return ShotAnalysis(
        id=shot_id,
        asset_id=asset_id,
        range=TimeRange(start_seconds=start, end_seconds=end),
        mean_motion=0.5,
        peak_motion=1.0,
        motion_samples=[],
        edit_anchors=[],
        global_motion=GlobalMotionSummary(),
        occlusion=OcclusionCueSummary(
            peak_score=max((sample.score for sample in samples), default=0.0),
            mean_score=sum((sample.score for sample in samples), 0.0) / len(samples) if samples else 0.0,
            peak_time_seconds=max(samples, key=lambda sample: sample.score).time_seconds if samples else None,
            dominant_edge=max(samples, key=lambda sample: sample.score).dominant_edge if samples else "none",
            confidence=.8 if samples else 0.0,
            samples=samples,
        ),
    )


def _sample(time: float, score: float, edge: str = "left") -> OcclusionCueSample:
    return OcclusionCueSample(
        time_seconds=time,
        score=score,
        residual_change_fraction=.2,
        largest_component_fraction=.15,
        edge_contact_fraction=.6,
        dominant_edge=edge,
        compensation_confidence=.8,
    )


def _plan() -> EditPlan:
    return EditPlan(
        project_id="p",
        target_duration_seconds=4,
        actual_duration_seconds=4,
        segments=[
            EditSegment(
                id="left", asset_id="a", shot_id="sa",
                source_in_seconds=.5, source_out_seconds=2.0,
                timeline_in_seconds=0, timeline_out_seconds=2,
                role="build", target_energy=.5, shot_energy=.5, confidence=.9, reason="fixture",
            ),
            EditSegment(
                id="right", asset_id="b", shot_id="sb",
                source_in_seconds=1.0, source_out_seconds=2.8,
                timeline_in_seconds=2, timeline_out_seconds=4,
                role="reveal", target_energy=.5, shot_energy=.5, confidence=.9, reason="fixture",
            ),
        ],
    )


def test_outgoing_occlusion_near_cut_becomes_boundary_evidence():
    vir = VirProject.new("p", [
        _shot("sa", "a", 0, 3, [_sample(1.9, .82, "left")]),
        _shot("sb", "b", 0, 3, []),
    ])

    boundary = synthesize_transition_opportunities(_plan(), vir).boundaries[0]

    assert boundary.occlusion_candidate_score == .82
    assert boundary.occlusion_side == "outgoing"
    assert boundary.occlusion_edge == "left"


def test_distant_occlusion_does_not_motivate_boundary():
    vir = VirProject.new("p", [
        _shot("sa", "a", 0, 3, [_sample(.8, .9, "left")]),
        _shot("sb", "b", 0, 3, []),
    ])

    boundary = synthesize_transition_opportunities(_plan(), vir).boundaries[0]

    assert boundary.occlusion_candidate_score == 0.0
    assert boundary.occlusion_side == "none"
    assert boundary.occlusion_edge == "none"


def test_occlusion_on_both_sides_is_preserved_without_inventing_a_single_edge():
    vir = VirProject.new("p", [
        _shot("sa", "a", 0, 3, [_sample(1.9, .76, "left")]),
        _shot("sb", "b", 0, 3, [_sample(1.1, .72, "right")]),
    ])

    boundary = synthesize_transition_opportunities(_plan(), vir).boundaries[0]

    assert boundary.occlusion_candidate_score == .76
    assert boundary.occlusion_side == "both"
    assert boundary.occlusion_edge == "mixed"
