from datetime import datetime, timezone

from monter_bridge.analysis_models import EditAnchor, ShotAnalysis, TimeRange, VirProject
from monter_bridge.director import default_director_plan
from monter_bridge.microscope_models import StyleProfile
from monter_bridge.planner import build_edit_plan, snapped_boundaries, style_guided_segment_count


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


def style_profile(median_shot: float, confidence: float) -> StyleProfile:
    return StyleProfile(
        profile_name="KAREEM-SET-001",
        created_at=datetime.now(timezone.utc).isoformat(),
        source_labels=["edit-01"],
        videos_analyzed=1,
        cuts_analyzed=20,
        mean_shot_duration_seconds=median_shot,
        median_shot_duration_seconds=median_shot,
        fast_cut_rate=0.5,
        long_hold_rate=0.2,
        direction_continuity_rate=0.5,
        action_phase_cut_rate=0.4,
        deliberate_discontinuity_rate=0.25,
        motion_match_opportunity_rate=0.5,
        median_relation_score=0.55,
        normalized_energy_arc=[0.5] * 24,
        direction_distribution={"right": 1.0},
        confidence=confidence,
        interpretation=[],
        limitations=[],
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


def test_high_confidence_fast_style_increases_cutting_density():
    profile = style_profile(median_shot=0.75, confidence=1.0)
    assert style_guided_segment_count(8.0, default_count=4, style_profile=profile) == 11

    vir = VirProject.new("project_test", [shot(index, 0.5 + index) for index in range(8)])
    edit = build_edit_plan(vir, default_director_plan(8.0), style_profile=profile)

    assert len(edit.segments) == 11
    assert any("KAREEM-SET-001" in note for note in edit.strategy_notes)


def test_low_confidence_style_stays_close_to_baseline():
    profile = style_profile(median_shot=0.5, confidence=0.1)
    count = style_guided_segment_count(15.0, default_count=6, style_profile=profile)

    assert count == 7
    assert count < 12
