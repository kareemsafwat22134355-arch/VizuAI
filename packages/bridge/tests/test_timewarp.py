from monter_bridge.analysis_models import EditAnchor, ShotAnalysis, TimeRange, VirProject
from monter_bridge.planning_models import EditPlan, EditSegment
from monter_bridge.timewarp import build_timewarp_intent, select_timewarp_intents, timewarp_output_duration


def fixture_segment(id_: str = "s1", role: str = "barrage") -> EditSegment:
    return EditSegment(
        id=id_, asset_id="a", shot_id="shot_a",
        source_in_seconds=1, source_out_seconds=4,
        timeline_in_seconds=0, timeline_out_seconds=3,
        role=role, target_energy=.8, shot_energy=.9, confidence=.9, reason="fixture",
    )


def fixture_shot() -> ShotAnalysis:
    return ShotAnalysis(
        id="shot_a", asset_id="a", range=TimeRange(start_seconds=0, end_seconds=5),
        mean_motion=1, peak_motion=4, motion_samples=[],
        edit_anchors=[EditAnchor(type="motion_peak", time_seconds=2.5, confidence=.95, reason="event")],
    )


def test_timewarp_is_anchored_and_preserves_output_duration():
    segment = fixture_segment()
    intent = build_timewarp_intent(segment, fixture_shot())
    assert intent is not None
    assert intent.anchor_seconds == 2.5
    assert len(intent.slices) == 3
    assert intent.slices[1].playback_rate > intent.slices[0].playback_rate
    assert abs(timewarp_output_duration(intent) - 3.0) < 1e-9


def test_selector_limits_timewarps_to_requested_count():
    shot_a = fixture_shot()
    shot_b = shot_a.model_copy(update={"id": "shot_b", "asset_id": "b", "peak_motion": 5})
    segments = [fixture_segment("s1"), fixture_segment("s2")]
    segments[1].asset_id = "b"
    segments[1].shot_id = "shot_b"
    segments[1].timeline_in_seconds = 3
    segments[1].timeline_out_seconds = 6
    edit = EditPlan(project_id="p", target_duration_seconds=6, actual_duration_seconds=6, segments=segments)
    vir = VirProject.new("p", [shot_a, shot_b])

    intents = select_timewarp_intents(edit, vir, max_intents=1)
    assert len(intents) == 1
