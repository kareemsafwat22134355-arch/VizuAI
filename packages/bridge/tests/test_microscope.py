from datetime import datetime, timezone
from pathlib import Path

import pytest

import monter_bridge.microscope as microscope_module
from monter_bridge.analysis_models import TimeRange
from monter_bridge.microscope import aggregate_style_profile, inspect_finished_video
from monter_bridge.microscope_models import MicroscopeReport, ObservedCut
from monter_bridge.cut_signature import CutSignature
from monter_bridge.models import MediaTechnical


def _cut(index: int, relation: float, direction: float, phase: float) -> ObservedCut:
    return ObservedCut(
        index=index,
        time_seconds=float(index),
        left_shot_id=f"left_{index}",
        right_shot_id=f"right_{index}",
        left_duration_seconds=1.0,
        right_duration_seconds=1.0,
        signature=CutSignature(
            direction_compatibility=direction,
            zoom_compatibility=0.7,
            phase_compatibility=phase,
            global_motion_confidence=0.8,
            relation_score=relation,
        ),
        classification="test",
    )


def _report(label: str, durations: list[float], cuts: list[ObservedCut], arc_value: float) -> MicroscopeReport:
    import numpy as np

    values = np.array(durations, dtype=float)
    return MicroscopeReport(
        source_label=label,
        source_duration_seconds=float(values.sum()),
        created_at=datetime.now(timezone.utc).isoformat(),
        shot_count=len(durations),
        cut_count=len(cuts),
        shot_durations_seconds=durations,
        mean_shot_duration_seconds=float(values.mean()),
        median_shot_duration_seconds=float(np.median(values)),
        p25_shot_duration_seconds=float(np.percentile(values, 25)),
        p75_shot_duration_seconds=float(np.percentile(values, 75)),
        fast_cut_rate=sum(value < 0.8 for value in durations) / len(durations),
        long_hold_rate=sum(value > 2.0 for value in durations) / len(durations),
        direction_continuity_rate=sum(cut.signature.direction_compatibility >= 0.9 for cut in cuts) / len(cuts) if cuts else 0,
        action_phase_cut_rate=sum(cut.signature.phase_compatibility >= 0.6 for cut in cuts) / len(cuts) if cuts else 0,
        deliberate_discontinuity_rate=sum(cut.signature.relation_score < 0.35 for cut in cuts) / len(cuts) if cuts else 0,
        motion_match_opportunity_rate=sum(cut.signature.relation_score >= 0.55 for cut in cuts) / len(cuts) if cuts else 0,
        median_relation_score=float(np.median([cut.signature.relation_score for cut in cuts])) if cuts else 0,
        motion_energy_arc=[arc_value] * 24,
        direction_distribution={"right": 1.0},
        cuts=cuts,
        limitations=[],
    )


def test_style_profile_weights_by_observed_shots_and_cuts():
    fast = _report(
        "fast",
        [0.5, 0.6, 0.7],
        [_cut(1, 0.8, 1.0, 0.8), _cut(2, 0.7, 1.0, 0.7)],
        0.9,
    )
    slow = _report(
        "slow",
        [2.5, 3.0],
        [_cut(1, 0.2, 0.0, 0.1)],
        0.1,
    )

    profile = aggregate_style_profile([fast, slow], profile_name="KAREEM-SET")

    assert profile.videos_analyzed == 2
    assert profile.cuts_analyzed == 3
    assert profile.fast_cut_rate == pytest.approx(3 / 5)
    assert profile.long_hold_rate == pytest.approx(2 / 5)
    assert profile.direction_continuity_rate == pytest.approx(2 / 3)
    assert profile.action_phase_cut_rate == pytest.approx(2 / 3)
    assert profile.deliberate_discontinuity_rate == pytest.approx(1 / 3)
    assert len(profile.normalized_energy_arc) == 24
    assert profile.normalized_energy_arc[0] == pytest.approx(0.5)
    assert profile.confidence > 0
    assert profile.interpretation


def test_inspector_keeps_portable_source_label_and_handles_motionless_shots(monkeypatch):
    monkeypatch.setattr(
        microscope_module,
        "probe_media",
        lambda path: MediaTechnical(duration_seconds=3.0, width=320, height=180, fps=12, codec="h264", has_audio=False),
    )
    monkeypatch.setattr(
        microscope_module,
        "detect_shots",
        lambda path: [
            TimeRange(start_seconds=0.0, end_seconds=1.0),
            TimeRange(start_seconds=1.0, end_seconds=2.0),
            TimeRange(start_seconds=2.0, end_seconds=3.0),
        ],
    )
    monkeypatch.setattr(microscope_module, "sample_motion_signals", lambda *args, **kwargs: ([], [], []))

    report = inspect_finished_video(Path("/private/user/path/edit.mp4"), source_label="Manual Edit 01")

    assert report.source_label == "Manual Edit 01"
    assert report.shot_count == 3
    assert report.cut_count == 2
    assert report.median_shot_duration_seconds == pytest.approx(1.0)
    assert report.motion_energy_arc == [0.0] * 24
    assert all(cut.classification == "deliberate_discontinuity" for cut in report.cuts)
    assert "/private/user/path" not in report.model_dump_json()


def test_style_profile_requires_reports():
    with pytest.raises(ValueError, match="At least one"):
        aggregate_style_profile([])
