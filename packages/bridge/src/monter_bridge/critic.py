from __future__ import annotations

from collections import Counter

from .analysis_models import VirProject
from .ctl_models import CtlProgram
from .critic_models import CriticFinding, CriticMetric, CriticReport
from .motion_match_realign import propose_motion_match_realign
from .planning_models import EditPlan

CORE_REVISION_METRICS = {
    "duration_error_seconds",
    "mean_energy_error",
    "low_confidence_ratio",
    "adjacent_repeat_count",
    "recoverable_motion_match_timing_count",
}


def critique_edit(edit: EditPlan, ctl: CtlProgram, vir: VirProject) -> CriticReport:
    findings: list[CriticFinding] = []
    metrics: list[CriticMetric] = []

    duration_error = abs(edit.actual_duration_seconds - edit.target_duration_seconds)
    duration_tolerance = max(0.05, edit.target_duration_seconds * 0.02)
    metrics.append(CriticMetric(
        name="duration_error_seconds",
        value=duration_error,
        target=f"<= {duration_tolerance:.3f}",
        passed=duration_error <= duration_tolerance,
    ))
    if duration_error > duration_tolerance:
        findings.append(CriticFinding(
            code="duration_mismatch", severity="error",
            message=f"Edit duration misses target by {duration_error:.2f}s.",
        ))

    energy_errors = [abs(segment.target_energy - segment.shot_energy) for segment in edit.segments]
    mean_energy_error = sum(energy_errors) / len(energy_errors) if energy_errors else 1.0
    metrics.append(CriticMetric(
        name="mean_energy_error", value=mean_energy_error,
        target="<= 0.30", passed=mean_energy_error <= 0.30,
    ))
    for segment, error in zip(edit.segments, energy_errors):
        if error > 0.45:
            findings.append(CriticFinding(
                code="energy_mismatch", severity="warning", segment_id=segment.id,
                message=f"Segment energy differs from director target by {error:.2f}.",
            ))

    low_confidence = [segment for segment in edit.segments if segment.confidence < 0.45]
    low_confidence_ratio = len(low_confidence) / len(edit.segments) if edit.segments else 1.0
    metrics.append(CriticMetric(
        name="low_confidence_ratio", value=low_confidence_ratio,
        target="<= 0.20", passed=low_confidence_ratio <= 0.20,
    ))
    for segment in low_confidence:
        findings.append(CriticFinding(
            code="low_confidence_selection", severity="warning", segment_id=segment.id,
            message=f"Selection confidence is only {segment.confidence:.2f}.",
        ))

    repeated_adjacent = 0
    for left, right in zip(edit.segments, edit.segments[1:]):
        if left.shot_id == right.shot_id:
            repeated_adjacent += 1
            findings.append(CriticFinding(
                code="immediate_repetition", severity="error", segment_id=right.id,
                message="The same shot is used in adjacent segments.",
            ))
    metrics.append(CriticMetric(
        name="adjacent_repeat_count", value=float(repeated_adjacent),
        target="0", passed=repeated_adjacent == 0,
    ))

    short_segments = [segment for segment in edit.segments if segment.timeline_out_seconds - segment.timeline_in_seconds < 0.55]
    metrics.append(CriticMetric(
        name="sub_550ms_segment_count", value=float(len(short_segments)),
        target="0 unless intentionally motivated", passed=len(short_segments) == 0,
    ))
    for segment in short_segments:
        findings.append(CriticFinding(
            code="overcut_risk", severity="warning", segment_id=segment.id,
            message="Segment is shorter than 550ms and may read as accidental overcutting.",
        ))

    mechanism_counts = Counter(transition.mechanism for transition in ctl.transitions)
    dominant_ratio = max(mechanism_counts.values(), default=0) / len(ctl.transitions) if ctl.transitions else 0.0
    metrics.append(CriticMetric(
        name="dominant_transition_ratio", value=dominant_ratio,
        target="<= 0.85 (hard cuts may intentionally dominate)",
        passed=dominant_ratio <= 0.85 or set(mechanism_counts) == {"hard_cut"},
    ))
    if dominant_ratio > 0.85 and set(mechanism_counts) != {"hard_cut"}:
        findings.append(CriticFinding(
            code="transition_repetition", severity="warning",
            message="One non-trivial transition mechanism dominates almost every boundary.",
        ))

    deliberate_hard_cuts = mechanism_counts.get("hard_cut", 0)
    metrics.append(CriticMetric(
        name="hard_cut_count", value=float(deliberate_hard_cuts),
        target=">= 1 when more than one boundary exists",
        passed=len(ctl.transitions) <= 1 or deliberate_hard_cuts >= 1,
    ))
    if len(ctl.transitions) > 1 and deliberate_hard_cuts == 0:
        findings.append(CriticFinding(
            code="no_deliberate_hard_cut", severity="warning",
            message="Every boundary is labeled with a mechanism; preserve at least one deliberate hard cut.",
        ))

    # Only motion_match_cut boundaries are eligible for source-trim timing repair.
    # Deliberate hard cuts are never turned into action cuts by this heuristic.
    warped_segment_ids = {warp.segment_id for warp in ctl.time_warps}
    recoverable_motion_match_timing = 0
    for transition in ctl.transitions:
        if transition.mechanism != "motion_match_cut":
            continue
        boundary_index = transition.boundary_index
        if boundary_index < 1 or boundary_index >= len(edit.segments):
            continue
        left = edit.segments[boundary_index - 1]
        right = edit.segments[boundary_index]
        if left.id in warped_segment_ids or right.id in warped_segment_ids:
            continue
        proposal = propose_motion_match_realign(edit, vir, boundary_index)
        if proposal is None:
            continue
        recoverable_motion_match_timing += 1
        findings.append(CriticFinding(
            code="motion_match_timing_weak",
            severity="warning",
            boundary_index=boundary_index,
            message=(
                f"Motion-match boundary {boundary_index} has phase compatibility "
                f"{proposal.before_phase_compatibility:.2f}, but bounded source-trim shifts "
                f"({proposal.left_shift_seconds:+.3f}s / {proposal.right_shift_seconds:+.3f}s) "
                f"can raise it to {proposal.after_phase_compatibility:.2f}."
            ),
        ))
    metrics.append(CriticMetric(
        name="recoverable_motion_match_timing_count",
        value=float(recoverable_motion_match_timing),
        target="0 recoverable weak-timing motion-match boundaries",
        passed=recoverable_motion_match_timing == 0,
    ))

    if vir.warnings:
        findings.append(CriticFinding(
            code="analysis_warnings", severity="warning",
            message=f"VIR contains {len(vir.warnings)} analysis warning(s); review before trusting all selections.",
        ))

    core_metric_failed = any(metric.name in CORE_REVISION_METRICS and not metric.passed for metric in metrics)
    has_error = any(finding.severity == "error" for finding in findings)
    status = "needs_revision" if has_error or core_metric_failed else "pass"

    return CriticReport(
        project_id=edit.project_id,
        status=status,
        metrics=metrics,
        findings=findings,
        notes=[
            "Metrics remain separate by design; MONTER does not collapse editorial quality into one aggregate score.",
            "Core metric failures trigger a bounded revision pass; other warnings can remain intentional editorial choices.",
            "Source-trim timing repair is considered only for existing motion_match_cut boundaries with strong reachable motion anchors and no adjacent timewarp.",
        ],
    )
