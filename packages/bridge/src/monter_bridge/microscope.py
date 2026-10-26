from __future__ import annotations

import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from .analysis import sample_motion_signals
from .analysis_models import ShotAnalysis
from .cut_signature import build_cut_signature
from .ffprobe import probe_media
from .global_motion import summarize_global_motion
from .microscope_models import MicroscopeReport, ObservedCut, StyleProfile
from .motion import build_motion_anchors
from .planning_models import EditSegment
from .shots import detect_shots

ENERGY_BINS = 24
FAST_SHOT_SECONDS = 0.8
LONG_HOLD_SECONDS = 2.0


def _safe_rate(count: int, total: int) -> float:
    return count / total if total else 0.0


def _normalized_shot_energy(shots: list[ShotAnalysis]) -> dict[str, float]:
    values = np.array([shot.mean_motion for shot in shots], dtype=np.float64)
    if not len(values):
        return {}
    low = float(values.min())
    high = float(values.max())
    if high - low <= 1e-9:
        return {shot.id: 0.5 if high > 0 else 0.0 for shot in shots}
    return {shot.id: float((shot.mean_motion - low) / (high - low)) for shot in shots}


def _energy_arc(shots: list[ShotAnalysis], duration: float, bins: int = ENERGY_BINS) -> list[float]:
    if not shots or duration <= 0 or bins <= 0:
        return []
    energies = _normalized_shot_energy(shots)
    result: list[float] = []
    for index in range(bins):
        t = duration * (index + 0.5) / bins
        shot = next(
            (candidate for candidate in shots if candidate.range.start_seconds <= t <= candidate.range.end_seconds),
            min(shots, key=lambda candidate: abs((candidate.range.start_seconds + candidate.range.end_seconds) / 2 - t)),
        )
        result.append(energies.get(shot.id, 0.0))
    return result


def _direction_distribution(shots: list[ShotAnalysis]) -> dict[str, float]:
    counts = Counter(shot.global_motion.dominant_screen_direction for shot in shots)
    total = sum(counts.values())
    return {direction: count / total for direction, count in sorted(counts.items())} if total else {}


def _observed_segment(shot: ShotAnalysis, index: int, energy: float) -> EditSegment:
    return EditSegment(
        id=f"observed_{index:04d}",
        asset_id="finished_master",
        shot_id=shot.id,
        source_in_seconds=shot.range.start_seconds,
        source_out_seconds=shot.range.end_seconds,
        timeline_in_seconds=shot.range.start_seconds,
        timeline_out_seconds=shot.range.end_seconds,
        role="build",
        target_energy=energy,
        shot_energy=energy,
        confidence=1.0,
        reason="Observed timing from a finished human edit; not an AI planning decision.",
    )


def _classify_cut(signature) -> str:
    if (
        signature.direction_compatibility >= 0.9
        and signature.global_motion_confidence >= 0.35
        and signature.relation_score >= 0.55
    ):
        return "motion_continuity"
    if signature.phase_compatibility >= 0.6:
        return "action_phase"
    if signature.relation_score < 0.35:
        return "deliberate_discontinuity"
    return "neutral_physical_cut"


def inspect_finished_video(video_path: Path, source_label: str | None = None) -> MicroscopeReport:
    technical = probe_media(video_path)
    if technical.duration_seconds <= 0:
        raise ValueError(f"Could not determine positive duration for finished edit: {video_path}")

    ranges = detect_shots(video_path)
    if not ranges:
        raise ValueError(f"No shots detected in finished edit: {video_path}")

    shots: list[ShotAnalysis] = []
    for index, shot_range in enumerate(ranges):
        motion_samples, global_samples = sample_motion_signals(video_path, shot_range)
        magnitudes = [sample.magnitude for sample in motion_samples]
        shots.append(
            ShotAnalysis(
                id=f"observed_shot_{index:04d}",
                asset_id="finished_master",
                range=shot_range,
                mean_motion=float(np.mean(magnitudes)) if magnitudes else 0.0,
                peak_motion=max(magnitudes, default=0.0),
                motion_samples=motion_samples,
                edit_anchors=build_motion_anchors(motion_samples, shot_range),
                global_motion=summarize_global_motion(global_samples),
            )
        )

    energies = _normalized_shot_energy(shots)
    segments = [_observed_segment(shot, index, energies.get(shot.id, 0.0)) for index, shot in enumerate(shots)]

    cuts: list[ObservedCut] = []
    for index, (left, right, left_segment, right_segment) in enumerate(
        zip(shots, shots[1:], segments, segments[1:]),
        start=1,
    ):
        signature = build_cut_signature(left_segment, right_segment, left, right)
        cuts.append(
            ObservedCut(
                index=index,
                time_seconds=left.range.end_seconds,
                left_shot_id=left.id,
                right_shot_id=right.id,
                left_duration_seconds=left.range.duration_seconds,
                right_duration_seconds=right.range.duration_seconds,
                signature=signature,
                classification=_classify_cut(signature),
            )
        )

    durations = np.array([shot.range.duration_seconds for shot in shots], dtype=np.float64)
    relation_scores = np.array([cut.signature.relation_score for cut in cuts], dtype=np.float64)
    cut_count = len(cuts)
    label = source_label or video_path.name

    return MicroscopeReport(
        **MicroscopeReport.empty_metadata(label, technical.duration_seconds),
        shot_count=len(shots),
        cut_count=cut_count,
        shot_durations_seconds=[float(value) for value in durations],
        mean_shot_duration_seconds=float(np.mean(durations)),
        median_shot_duration_seconds=float(np.median(durations)),
        p25_shot_duration_seconds=float(np.percentile(durations, 25)),
        p75_shot_duration_seconds=float(np.percentile(durations, 75)),
        fast_cut_rate=float(np.mean(durations < FAST_SHOT_SECONDS)),
        long_hold_rate=float(np.mean(durations > LONG_HOLD_SECONDS)),
        direction_continuity_rate=_safe_rate(sum(cut.signature.direction_compatibility >= 0.9 for cut in cuts), cut_count),
        action_phase_cut_rate=_safe_rate(sum(cut.signature.phase_compatibility >= 0.6 for cut in cuts), cut_count),
        deliberate_discontinuity_rate=_safe_rate(sum(cut.signature.relation_score < 0.35 for cut in cuts), cut_count),
        motion_match_opportunity_rate=_safe_rate(sum(cut.signature.relation_score >= 0.55 for cut in cuts), cut_count),
        median_relation_score=float(np.median(relation_scores)) if cut_count else 0.0,
        motion_energy_arc=_energy_arc(shots, technical.duration_seconds),
        direction_distribution=_direction_distribution(shots),
        cuts=cuts,
        limitations=[
            "Microscope v0.1 measures timing and physical motion evidence only; it does not yet infer semantics, gaze, attention, composition, color intent, narrative meaning, or audio-cut causality.",
            "Scene detection on dissolves, flashes, or heavily composited transitions can produce approximate rather than editorially exact boundaries.",
            "A low relation score means weak physical continuity evidence, not a bad cut; deliberate discontinuity can be stylistically correct.",
        ],
    )


def _weighted_rate(reports: list[MicroscopeReport], field: str, weight_field: str) -> float:
    total_weight = sum(getattr(report, weight_field) for report in reports)
    if total_weight <= 0:
        return 0.0
    return sum(getattr(report, field) * getattr(report, weight_field) for report in reports) / total_weight


def _profile_interpretation(
    median_duration: float,
    fast_rate: float,
    long_hold_rate: float,
    direction_rate: float,
    phase_rate: float,
    discontinuity_rate: float,
) -> list[str]:
    findings: list[str] = []
    if median_duration < 1.0:
        findings.append("The observed baseline favors dense shot turnover rather than long uninterrupted holds.")
    elif median_duration > 2.0:
        findings.append("The observed baseline favors patient holds and lets individual shots carry more time.")
    else:
        findings.append("The observed baseline balances fast turnover with readable shot holds.")

    if fast_rate >= 0.35 and long_hold_rate >= 0.15:
        findings.append("Rhythm relies on contrast: short bursts coexist with deliberate longer holds instead of one constant cutting rate.")
    if direction_rate >= 0.4:
        findings.append("Screen-motion direction is frequently preserved across cuts, suggesting continuity is often carried by movement rather than effects.")
    if phase_rate >= 0.35:
        findings.append("A meaningful share of cuts land near measured motion phases, consistent with cut-on-action behavior.")
    if discontinuity_rate >= 0.35:
        findings.append("The style tolerates or favors physically discontinuous cuts; MONTER should not force motion matching at every boundary.")
    if not findings:
        findings.append("The current motion/rhythm sample is mixed; more finished edits are needed before enforcing a strong policy.")
    return findings


def aggregate_style_profile(reports: list[MicroscopeReport], profile_name: str = "MONTER Style Profile") -> StyleProfile:
    if not reports:
        raise ValueError("At least one microscope report is required")

    all_durations = np.array(
        [duration for report in reports for duration in report.shot_durations_seconds],
        dtype=np.float64,
    )
    all_relation_scores = np.array(
        [cut.signature.relation_score for report in reports for cut in report.cuts],
        dtype=np.float64,
    )
    cuts_analyzed = sum(report.cut_count for report in reports)
    shots_analyzed = sum(report.shot_count for report in reports)

    energy_arcs = [report.motion_energy_arc for report in reports if len(report.motion_energy_arc) == ENERGY_BINS]
    normalized_energy_arc = (
        [float(value) for value in np.mean(np.array(energy_arcs, dtype=np.float64), axis=0)]
        if energy_arcs
        else []
    )

    direction_counts: Counter[str] = Counter()
    for report in reports:
        for direction, fraction in report.direction_distribution.items():
            direction_counts[direction] += fraction * report.shot_count
    direction_total = sum(direction_counts.values())
    direction_distribution = (
        {direction: count / direction_total for direction, count in sorted(direction_counts.items())}
        if direction_total
        else {}
    )

    fast_rate = _weighted_rate(reports, "fast_cut_rate", "shot_count")
    long_hold_rate = _weighted_rate(reports, "long_hold_rate", "shot_count")
    direction_rate = _weighted_rate(reports, "direction_continuity_rate", "cut_count")
    phase_rate = _weighted_rate(reports, "action_phase_cut_rate", "cut_count")
    discontinuity_rate = _weighted_rate(reports, "deliberate_discontinuity_rate", "cut_count")
    motion_match_rate = _weighted_rate(reports, "motion_match_opportunity_rate", "cut_count")
    median_duration = float(np.median(all_durations))

    return StyleProfile(
        profile_name=profile_name,
        created_at=datetime.now(timezone.utc).isoformat(),
        source_labels=[report.source_label for report in reports],
        videos_analyzed=len(reports),
        cuts_analyzed=cuts_analyzed,
        mean_shot_duration_seconds=float(np.mean(all_durations)),
        median_shot_duration_seconds=median_duration,
        fast_cut_rate=fast_rate,
        long_hold_rate=long_hold_rate,
        direction_continuity_rate=direction_rate,
        action_phase_cut_rate=phase_rate,
        deliberate_discontinuity_rate=discontinuity_rate,
        motion_match_opportunity_rate=motion_match_rate,
        median_relation_score=float(np.median(all_relation_scores)) if cuts_analyzed else 0.0,
        normalized_energy_arc=normalized_energy_arc,
        direction_distribution=direction_distribution,
        confidence=min(1.0, math.sqrt(max(0, cuts_analyzed) / 80.0)),
        interpretation=_profile_interpretation(
            median_duration,
            fast_rate,
            long_hold_rate,
            direction_rate,
            phase_rate,
            discontinuity_rate,
        ),
        limitations=[
            "This profile is a conditional motion/rhythm prior, not a complete representation of editorial taste.",
            "Semantic intent, attention, composition, color, sound-design causality, narrative function, and human correction history are not yet modeled in v0.1.",
            f"Profile contains {shots_analyzed} detected shots and {cuts_analyzed} observed cut boundaries across {len(reports)} finished edits.",
        ],
    )
