from monter_bridge.analysis_models import (
    EditAnchor,
    GlobalMotionSummary,
    ShotAnalysis,
    TimeRange,
    VirProject,
)
from monter_bridge.planning_models import EditPlan, EditSegment
from monter_bridge.transition_opportunities import synthesize_transition_opportunities


def shot(
    shot_id: str,
    start: float,
    end: float,
    direction: str = "right",
    zoom: str = "static",
    confidence: float = 0.8,
) -> ShotAnalysis:
    midpoint = (start + end) / 2
    return ShotAnalysis(
        id=shot_id,
        asset_id=f"asset_{shot_id}",
        range=TimeRange(start_seconds=start, end_seconds=end),
        mean_motion=1.0,
        peak_motion=2.0,
        motion_samples=[],
        edit_anchors=[
            EditAnchor(type="motion_onset", time_seconds=start + 0.4, confidence=0.8, reason="fixture"),
            EditAnchor(type="motion_peak", time_seconds=midpoint, confidence=0.9, reason="fixture"),
            EditAnchor(type="motion_settle", time_seconds=end - 0.4, confidence=0.7, reason="fixture"),
        ],
        global_motion=GlobalMotionSummary(
            dominant_screen_direction=direction,
            zoom_direction=zoom,
            mean_translation_x=2.0,
            mean_translation_y=0.0,
            mean_rotation_degrees=0.0,
            mean_scale_delta=0.01 if zoom == "in" else (-0.01 if zoom == "out" else 0.0),
            confidence=confidence,
            samples=[],
        ),
    )


def plan(left_out: float, right_in: float) -> EditPlan:
    return EditPlan(
        project_id="p",
        target_duration_seconds=4.0,
        actual_duration_seconds=4.0,
        segments=[
            EditSegment(
                id="left",
                asset_id="asset_left",
                shot_id="left_shot",
                source_in_seconds=0.5,
                source_out_seconds=left_out,
                timeline_in_seconds=0.0,
                timeline_out_seconds=2.0,
                role="build",
                target_energy=0.5,
                shot_energy=0.5,
                confidence=0.9,
                reason="fixture",
            ),
            EditSegment(
                id="right",
                asset_id="asset_right",
                shot_id="right_shot",
                source_in_seconds=right_in,
                source_out_seconds=7.0,
                timeline_in_seconds=2.0,
                timeline_out_seconds=4.0,
                role="escalate",
                target_energy=0.7,
                shot_energy=0.7,
                confidence=0.9,
                reason="fixture",
            ),
        ],
    )


def fixture_vir(zoom: str = "static") -> VirProject:
    return VirProject.new(
        "p",
        [
            shot("left_shot", 0.0, 4.0, direction="right", zoom=zoom),
            shot("right_shot", 4.0, 8.0, direction="right", zoom=zoom),
        ],
    )


def candidate(report, mechanism: str):
    return next(item for item in report.boundaries[0].candidates if item.mechanism == mechanism)


def test_directional_bridge_requires_handles_even_with_strong_motion_match():
    # Left ends only 0.02s before its shot boundary and right starts only 0.02s after its boundary.
    report = synthesize_transition_opportunities(plan(left_out=3.98, right_in=4.02), fixture_vir())

    bridge = candidate(report, "directional_bridge")
    assert bridge.feasible is False
    assert bridge.feasibility_score < 1.0
    assert report.boundaries[0].recommended_mechanism != "directional_bridge"
    assert candidate(report, "hard_cut").feasible is True


def test_directional_bridge_can_win_when_motion_and_handles_support_it():
    report = synthesize_transition_opportunities(plan(left_out=3.6, right_in=4.4), fixture_vir())

    bridge = candidate(report, "directional_bridge")
    assert bridge.feasible is True
    assert bridge.feasibility_score == 1.0
    assert bridge.parameters["screenDirection"] == "right"
    assert report.boundaries[0].recommended_mechanism in {"directional_bridge", "action_cut"}


def test_zoom_bridge_requires_shared_non_static_zoom_direction():
    zoom_report = synthesize_transition_opportunities(plan(left_out=3.6, right_in=4.4), fixture_vir(zoom="in"))
    static_report = synthesize_transition_opportunities(plan(left_out=3.6, right_in=4.4), fixture_vir(zoom="static"))

    assert candidate(zoom_report, "zoom_bridge").feasible is True
    assert candidate(static_report, "zoom_bridge").feasible is False


def test_report_keeps_hard_cut_first_class_at_every_boundary():
    report = synthesize_transition_opportunities(plan(left_out=3.98, right_in=4.02), fixture_vir())

    assert len(report.boundaries) == 1
    assert candidate(report, "hard_cut").duration_seconds == 0.0
    assert any("Hard cuts remain first-class" in note for note in report.notes)
