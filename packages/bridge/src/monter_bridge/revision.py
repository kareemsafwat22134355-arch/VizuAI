from __future__ import annotations

from copy import deepcopy

from .analysis_models import ShotAnalysis, VirProject
from .critic_models import CriticReport, RevisionAction, RevisionReport
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
    shots = {shot.id: shot for shot in vir.shots}
    energies = normalized_shot_energies(vir.shots)
    segment_by_id = {segment.id: segment for segment in revised.segments}
    actions: list[RevisionAction] = []

    replace_codes = {"energy_mismatch", "low_confidence_selection", "immediate_repetition"}
    requested_ids = []
    for finding in report.findings:
        if finding.code in replace_codes and finding.segment_id and finding.segment_id not in requested_ids:
            requested_ids.append(finding.segment_id)

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
        changed=any(action.kind == "replace_segment" for action in actions),
        actions=actions,
    )
