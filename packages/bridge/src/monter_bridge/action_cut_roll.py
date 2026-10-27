from __future__ import annotations

from pydantic import Field

from .analysis_models import VirProject
from .models import PortableModel
from .planning_models import EditPlan


class ActionCutBoundaryRoll(PortableModel):
    boundary_index: int = Field(ge=1)
    feasible: bool
    left_segment_id: str
    right_segment_id: str
    boundary_shift_seconds: float
    reason: str


def propose_action_cut_boundary_roll(
    edit: EditPlan,
    vir: VirProject,
    boundary_index: int,
    suggested_shift_seconds: float,
    *,
    max_shift_seconds: float = 0.45,
    min_segment_duration: float = 0.60,
) -> ActionCutBoundaryRoll | None:
    if boundary_index < 1 or boundary_index >= len(edit.segments):
        return None
    if abs(suggested_shift_seconds) > max_shift_seconds or abs(suggested_shift_seconds) < 1e-6:
        return None

    left = edit.segments[boundary_index - 1]
    right = edit.segments[boundary_index]
    shots = {shot.id: shot for shot in vir.shots}
    left_shot = shots.get(left.shot_id)
    right_shot = shots.get(right.shot_id)
    if left_shot is None or right_shot is None:
        return None

    delta = suggested_shift_seconds
    left_timeline_out = left.timeline_out_seconds + delta
    left_source_out = left.source_out_seconds + delta
    right_timeline_in = right.timeline_in_seconds + delta
    right_source_in = right.source_in_seconds + delta

    left_duration = left_timeline_out - left.timeline_in_seconds
    right_duration = right.timeline_out_seconds - right_timeline_in
    if left_duration < min_segment_duration or right_duration < min_segment_duration:
        return None

    if left_source_out <= left.source_in_seconds + 1e-6:
        return None
    if left_source_out > left_shot.range.end_seconds + 1e-6:
        return None
    if right_source_in < right_shot.range.start_seconds - 1e-6:
        return None
    if right_source_in >= right.source_out_seconds - 1e-6:
        return None

    if abs(left_timeline_out - right_timeline_in) > 1e-6:
        return None

    return ActionCutBoundaryRoll(
        boundary_index=boundary_index,
        feasible=True,
        left_segment_id=left.id,
        right_segment_id=right.id,
        boundary_shift_seconds=delta,
        reason=(
            "Reliable selective dense-flow timing evidence supports a common bounded action-cut shift; "
            "a roll edit can move the shared timeline/source boundary while preserving total sequence duration."
        ),
    )


def apply_action_cut_boundary_roll(edit: EditPlan, proposal: ActionCutBoundaryRoll) -> None:
    left = edit.segments[proposal.boundary_index - 1]
    right = edit.segments[proposal.boundary_index]
    if left.id != proposal.left_segment_id or right.id != proposal.right_segment_id:
        raise ValueError("Advanced action-cut roll proposal no longer matches the edit boundary")

    delta = proposal.boundary_shift_seconds
    left.timeline_out_seconds += delta
    left.source_out_seconds += delta
    right.timeline_in_seconds += delta
    right.source_in_seconds += delta
    left.reason = f"{left.reason} Advanced action timing rolled boundary {delta:+.3f}s."
    right.reason = f"{right.reason} Advanced action timing rolled boundary {delta:+.3f}s."
