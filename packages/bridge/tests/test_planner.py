from monter_bridge.analysis_models import EditAnchor, ShotAnalysis, TimeRange, VirProject
from monter_bridge.director import default_director_plan
from monter_bridge.planner import build_edit_plan, snapped_boundaries


def shot(index: int, motion: float) -> ShotAnalysis:
    start = index * 6.0
    end = start + 5.0
    return ShotAnalysis(
        id=f"shot_{index}",
        asset_id=f"asset_{index}",
        range=TimeRange(start_seconds=start, end_seconds=end),
        mean_motion=motion,
        peak_motion=motion * 1.3,
        motion_samples=[],
        edit_anchors=[
            EditAnchor(
                type="motion_peak",
                time_seconds=start + 2.5,
                confidence=0.9,
                reason="fixture peak",
            )
        ],
    )


def test_planner_hits_target_when_sources_are_long_enough():
    vir = VirProject.new("project_test", [shot(0, 0.2), shot(1, 1.0), shot(2, 2.0), shot(3, 4.0)])
    director = default_director_plan(8.0)
    edit = build_edit_plan(vir, director)

    assert len(edit.segments) == 4
    assert abs(edit.actual_duration_seconds - 8.0) < 1e-6
    assert all(segment.timeline_out_seconds > segment.timeline_in_seconds for segment in edit.segments)
    assert all(segment.source_out_seconds > segment.source_in_seconds for segment in edit.segments)
    assert all(
        left.shot_id != right.shot_id
        for left, right in zip(edit.segments, edit.segments[1:])
    )


def test_beat_snapping_only_moves_nearby_boundaries():
    boundaries = snapped_boundaries(8.0, 4, beats_seconds=[1.92, 4.5, 6.04], snap_window=0.12)
    assert boundaries[1] == 1.92
    assert boundaries[2] == 4.0
    assert boundaries[3] == 6.04
