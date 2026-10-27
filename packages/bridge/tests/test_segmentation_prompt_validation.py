from __future__ import annotations

import pytest
from pydantic import ValidationError

from monter_bridge.advanced_analysis import build_advanced_analysis_plan
from monter_bridge.analysis_models import OcclusionCueSample
from monter_bridge.ctl_models import CtlClip, CtlProgram, CtlTransition
from monter_bridge.cut_signature import CutSignature
from monter_bridge.segmentation_prompt_models import SegmentationPromptContext
from monter_bridge.transition_opportunities import (
    BoundaryTransitionOpportunity,
    TransitionCandidate,
    TransitionOpportunityReport,
)


def test_prompt_point_must_stay_inside_residual_component_box():
    with pytest.raises(ValidationError, match="point must lie inside"):
        SegmentationPromptContext(
            side="left",
            source_time_seconds=1.0,
            point_xy_norm=[.8, .5],
            box_xyxy_norm=[.05, .2, .35, .8],
            confidence=.8,
            occlusion_score=.8,
            dominant_edge="left",
        )


def test_strong_seed_outside_exact_analysis_window_does_not_schedule_segmentation():
    ctl = CtlProgram(
        project_id="p",
        duration_seconds=4,
        clips=[
            CtlClip(
                id="s1", asset_id="a", shot_id="sa",
                source_in_seconds=.4, source_out_seconds=2.0,
                timeline_in_seconds=0, timeline_out_seconds=2,
            ),
            CtlClip(
                id="s2", asset_id="b", shot_id="sb",
                source_in_seconds=1.0, source_out_seconds=2.8,
                timeline_in_seconds=2, timeline_out_seconds=4,
            ),
        ],
        transitions=[CtlTransition(
            boundary_index=1,
            mechanism="hard_cut",
            evidence={"adjacentTimewarp": False},
            reason="fixture",
        )],
        render_fps=24,
        render_width=960,
    )

    # The cue is within transition synthesis' broad ±0.45s neighborhood of source_out=2.0,
    # but it is earlier than the exact advanced left window start at 1.65s.
    seed = OcclusionCueSample(
        time_seconds=1.60,
        score=.88,
        residual_change_fraction=.25,
        largest_component_fraction=.2,
        largest_component_bbox_xywh_norm=[0.0, .2, .28, .6],
        largest_component_centroid_xy_norm=[.14, .5],
        edge_contact_fraction=.75,
        dominant_edge="left",
        compensation_confidence=.9,
    )
    candidate = TransitionCandidate(
        mechanism="hard_cut",
        duration_seconds=0,
        required_handle_seconds=0,
        feasible=True,
        feasibility_score=1,
        motivation_score=.8,
        relation_score=.4,
        reason="fixture",
    )
    boundary = BoundaryTransitionOpportunity(
        boundary_index=1,
        left_segment_id="s1",
        right_segment_id="s2",
        outgoing_handle_seconds=.3,
        incoming_handle_seconds=.3,
        cut_signature=CutSignature(
            direction_compatibility=.2,
            zoom_compatibility=.2,
            phase_compatibility=.2,
            global_motion_confidence=.5,
            relation_score=.4,
        ),
        recommended_mechanism="hard_cut",
        candidates=[candidate],
        occlusion_candidate_score=.88,
        occlusion_side="outgoing",
        occlusion_edge="left",
        outgoing_occlusion_seed=seed,
    )

    plan = build_advanced_analysis_plan(
        ctl,
        TransitionOpportunityReport(project_id="p", boundaries=[boundary]),
    )

    assert plan.requests == []
    assert plan.skipped_boundaries
