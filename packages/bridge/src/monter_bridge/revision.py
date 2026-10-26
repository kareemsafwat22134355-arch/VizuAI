from __future__ import annotations

from copy import deepcopy

from .analysis_models import ShotAnalysis, VirProject
from .critic_models import CriticReport, RevisionAction, RevisionReport
from .motion_match_realign import apply_motion_match_realign, propose_motion_match_realign
from .planner import normalized_shot_energies
from .planning_models import EditPlan


def _replacement_window(shot: ShotAnalysis, duration: float) -> tuple[float, float]:
    duration = min(duration, shot.range.duration_seconds)
    peak = next((anchor for anchor in shot.edit_anchors if anchor.type == "motion_peak"), None)
    center = peak.time_seconds if peak else (shot.range.start_seconds + shot.range.end_seconds) / 2
    start = center - duration * 0.45
    start = max(shot.range.start_seconds, min(start, shot.range.end_seconds - duration))
    return start, start + duration


def revise_edit_plan(edit: EditPlan, vir: VirProject, report: CriticReport) -> tuple[EditPlan, RevisionReport]:
    revised = deepcopy(edit)
    energies = normalized_shot_energies(vir.shots)
    segment_by_id = {segment.id: segment for segment in revised.segments}
    actions: list[RevisionAction] = []

    replace_codes = {"energy_mismatch", "low_confidence_selection", "immediate_repetition"}
    requested_ids: list[str] = []
    for finding in report.findings:
        if finding.code in replace_codes and finding.segment_id and finding.segment_id not in requested_ids:
            requested_ids.append(finding.segment_id)

    # Realign source trims first, but never on a boundary whose adjacent segment will be
    # replaced in the same revision pass. A replacement invalidates the original anchor evidence.
    requested_boundaries: list[int] = []
    for finding in report.findings:
        if (
            finding.code == "motion_match_timing_weak"
            and finding.boundary_index is not None
            and finding.boundary_index not in requested_boundaries
        ):
            requested_boundaries.append(finding.boundary_index)

    for boundary_index in requested_boundaries:
        if boundary_index < 1 or boundary_index >= len(revised.segments):
            continue
        left = revised.segments[boundary_index - 1]
        right = revised.segments[boundary_index]
        if left.id in requested_ids or right.id in requested_ids:
            continue
        proposal = propose_motion_match_realign(revised, vir, boundary_index)
        if proposal is None:
            continue
        apply_motion_match_realign(revised, proposal)
        actions.append(RevisionAction(
            kind="realign_boundary",
            reason=(
                "Critic identified a motion_match_cut with recoverable weak phase timing; "
                "source trims were shifted without changing timeline duration."
            ),
            boundary_index=boundary_index,
            left_shift_seconds=proposal.left_shift_seconds,
            right_shift_seconds=proposal.right_shift_seconds,
        ))

    segment_by_id = {segment.id: segment for segment in revised.segments}
    for segment_id in requested_ids:
        segment = segment_by_id.get(segment_id)
        if segment is None:
            continue
        duration = segment.timeline_out_seconds - segment.timeline_in_seconds
        index = revised.segments.index(segment)
        neighbor_ids = {
            revised.segments[index - 1].shot_id if index > 0 else None,
            revised.segments[index + 1].shot_id if index + 1 < len(revised.segments) else None,
        }
        candidates = [
            shot for shot in vir.shots
            if shot.id != segment.shot_id
            and shot.id not in neighbor_ids
            and shot.range.duration_seconds >= duration
        ]
        if not candidates:
            continue

        def score(shot: ShotAnalysis) -> float:
            return 1.0 - abs(energies[shot.id] - segment.target_energy)

        replacement = max(candidates, key=score)
        old_shot = segment.shot_id
        source_in, source_out = _replacement_window(replacement, duration)
        segment.asset_id = replacement.asset_id
        segment.shot_id = replacement.id
        segment.source_in_seconds = source_in
        segment.source_out_seconds = source_out
        segment.shot_energy = energies[replacement.id]
        segment.confidence = max(0.0, min(1.0, score(replacement)))
        segment.reason = (
            f"Revision replaced {old_shot} after critic feedback; new shot energy "
            f"{segment.shot_energy:.2f} targets {segment.target_energy:.2f}."
        )
        actions.append(RevisionAction(
            kind="replace_segment",
            reason="Critic identified repetition, energy mismatch, or weak selection confidence.",
            segment_id=segment.id,
            from_shot_id=old_shot,
            to_shot_id=replacement.id,
        ))

    for finding in report.findings:
        if finding.code == "duration_mismatch":
            actions.append(RevisionAction(kind="review_duration", reason=finding.message))
        elif finding.code in {"transition_repetition", "no_deliberate_hard_cut"}:
            actions.append(RevisionAction(kind="review_transition", reason=finding.message))
        elif finding.code == "analysis_warnings":
            actions.append(RevisionAction(kind="review_analysis", reason=finding.message))

    return revised, RevisionReport(
        project_id=edit.project_id,
        changed=any(action.kind in {"replace_segment", "realign_boundary"} for action in actions),
        actions=actions,
    )
