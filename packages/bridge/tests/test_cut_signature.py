from monter_bridge.analysis_models import GlobalMotionSummary, ShotAnalysis, TimeRange
from monter_bridge.cut_signature import build_cut_signature
from monter_bridge.planning_models import EditSegment


def shot(id_: str, direction: str, confidence: float = .8) -> ShotAnalysis:
    return ShotAnalysis(
        id=id_, asset_id=id_, range=TimeRange(start_seconds=0, end_seconds=4),
        mean_motion=1, peak_motion=2, motion_samples=[], edit_anchors=[],
        global_motion=GlobalMotionSummary(
            dominant_screen_direction=direction,
            zoom_direction="static",
            confidence=confidence,
        ),
    )


def segment(id_: str, shot_id: str, tin: float, tout: float) -> EditSegment:
    return EditSegment(
        id=id_, asset_id=shot_id, shot_id=shot_id,
        source_in_seconds=0, source_out_seconds=2,
        timeline_in_seconds=tin, timeline_out_seconds=tout,
        role="build", target_energy=.5, shot_energy=.5, confidence=.8, reason="fixture",
    )


def test_same_global_direction_scores_higher_than_opposite_direction():
    left = segment("s1", "a", 0, 2)
    right = segment("s2", "b", 2, 4)

    same = build_cut_signature(left, right, shot("a", "right"), shot("b", "right"))
    opposite = build_cut_signature(left, right, shot("a", "right"), shot("b", "left"))

    assert same.direction_compatibility == 1.0
    assert opposite.direction_compatibility == 0.0
    assert same.relation_score > opposite.relation_score
