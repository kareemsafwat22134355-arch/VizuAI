from __future__ import annotations

from copy import deepcopy

from pydantic import Field

from .analysis_models import ShotAnalysis, VirProject
from .cut_signature import build_cut_signature
from .models import PortableModel
from .planning_models import EditPlan, EditSegment


class MotionMatchRealignment(PortableModel):
    boundary_index: int = Field(ge=1)
    feasible: bool
    left_segment_id: str
    right_segment_id: str
    left_shift_seconds: float = 0.0
    right_shift_seconds: float = 0.0
    before_phase_compatibility: float = Field(ge=0, le=1)
    after_phase_compatibility: float = Field(ge=0, le=1)
    left_anchor_type: str | None = None
    right_anchor_type: str | None = None
    left_anchor_confidence: float | None = Field(default=None, ge=0, le=1)
    right_anchor_confidence: float | None = Field(default=None, ge=0, le=1)
    reason: str


def _shifted_segment(segment: EditSegment, shift: float) -> EditSegment:
    shifted = deepcopy(segment)
    shifted.source_in_seconds += shift
    shifted.source_out_seconds += shift
    return shifted


def _best_anchor_shift(
    segment: EditSegment,
    shot: ShotAnalysis,
    *,
    edge: str,
    anchor_types: set[str],
    max_shift_seconds: float,
    min_anchor_confidence: float,
) -> tuple[float, str, float] | None:
    edge_time = segment.source_out_seconds if edge == "out" else segment.source_in_seconds
    candidates = [
        anchor for anchor in shot.edit_anchors
        if anchor.type in anchor_types
        and anchor.confidence >= min_anchor_confidence
        and abs(anchor.time_seconds - edge_time) <= max_shift_seconds
    ]
    if not candidates:
        return None

    candidates.sort(
        key=lambda anchor: (
            abs(anchor.time_seconds - edge_time),
            -anchor.confidence,
        )
    )
    anchor = candidates[0]
    shift = anchor.time_seconds - edge_time
    shifted_in = segment.source_in_seconds + shift
    shifted_out = segment.source_out_seconds + shift
    if shifted_in < shot.range.start_seconds - 1e-6 or shifted_out > shot.range.end_seconds + 1e-6:
        return None
    return shift, anchor.type, anchor.confidence


def propose_motion_match_realign(
    edit: EditPlan,
    vir: VirProject,
    boundary_index: int,
    *,
    max_shift_seconds: float = 0.45,
    min_anchor_confidence: float = 0.75,
    minimum_phase_gain: float = 0.40,
) -> MotionMatchRealignment | None:
    if boundary_index < 1 or boundary_index >= len(edit.segments):
        return None

    left_segment = edit.segments[boundary_index - 1]
    right_segment = edit.segments[boundary_index]
    shots = {shot.id: shot for shot in vir.shots}
    left_shot = shots.get(left_segment.shot_id)
    right_shot = shots.get(right_segment.shot_id)
    if left_shot is None or right_shot is None:
        return None

    before = build_cut_signature(left_segment, right_segment, left_shot, right_shot)
    if before.phase_compatibility >= 0.60:
        return None

    left_choice = _best_anchor_shift(
        left_segment,
        left_shot,
        edge="out",
        anchor_types={"motion_peak"},
        max_shift_seconds=max_shift_seconds,
        min_anchor_confidence=min_anchor_confidence,
    )
    right_choice = _best_anchor_shift(
        right_segment,
        right_shot,
        edge="in",
        anchor_types={"motion_onset", "motion_peak"},
        max_shift_seconds=max_shift_seconds,
        min_anchor_confidence=min_anchor_confidence,
    )
    if left_choice is None or right_choice is None:
        return None

    left_shift, left_type, left_confidence = left_choice
    right_shift, right_type, right_confidence = right_choice
    proposed_left = _shifted_segment(left_segment, left_shift)
    proposed_right = _shifted_segment(right_segment, right_shift)
    after = build_cut_signature(proposed_left, proposed_right, left_shot, right_shot)
    gain = after.phase_compatibility - before.phase_compatibility
    if after.phase_compatibility < 0.90 or gain < minimum_phase_gain:
        return None

    return MotionMatchRealignment(
        boundary_index=boundary_index,
        feasible=True,
        left_segment_id=left_segment.id,
        right_segment_id=right_segment.id,
        left_shift_seconds=left_shift,
        right_shift_seconds=right_shift,
        before_phase_compatibility=before.phase_compatibility,
        after_phase_compatibility=after.phase_compatibility,
        left_anchor_type=left_type,
        right_anchor_type=right_type,
        left_anchor_confidence=left_confidence,
        right_anchor_confidence=right_confidence,
        reason=(
            "A confident outgoing motion peak and incoming motion onset/peak are reachable by bounded source-window shifts; "
            "timeline duration remains unchanged while motion-phase compatibility becomes action-grade."
        ),
    )


def apply_motion_match_realign(edit: EditPlan, proposal: MotionMatchRealignment) -> None:
    left = edit.segments[proposal.boundary_index - 1]
    right = edit.segments[proposal.boundary_index]
    if left.id != proposal.left_segment_id or right.id != proposal.right_segment_id:
        raise ValueError("Motion-match realignment proposal no longer matches the edit boundary")

    left.source_in_seconds += proposal.left_shift_seconds
    left.source_out_seconds += proposal.left_shift_seconds
    right.source_in_seconds += proposal.right_shift_seconds
    right.source_out_seconds += proposal.right_shift_seconds
    left.reason = (
        f"{left.reason} Source trim shifted {proposal.left_shift_seconds:+.3f}s to align outgoing motion phase."
    )
    right.reason = (
        f"{right.reason} Source trim shifted {proposal.right_shift_seconds:+.3f}s to align incoming motion phase."
    )
