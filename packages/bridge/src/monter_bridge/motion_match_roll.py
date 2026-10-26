from __future__ import annotations

from copy import deepcopy

from pydantic import Field

from .analysis_models import ShotAnalysis, VirProject
from .cut_signature import build_cut_signature
from .models import PortableModel
from .motion_match_realign import propose_motion_match_realign
from .planning_models import EditPlan, EditSegment


class MotionMatchBoundaryRoll(PortableModel):
    boundary_index: int = Field(ge=1)
    feasible: bool
    left_segment_id: str
    right_segment_id: str
    boundary_shift_seconds: float
    before_phase_compatibility: float = Field(ge=0, le=1)
    after_phase_compatibility: float = Field(ge=0, le=1)
    left_anchor_type: str | None = None
    right_anchor_type: str | None = None
    left_anchor_confidence: float | None = Field(default=None, ge=0, le=1)
    right_anchor_confidence: float | None = Field(default=None, ge=0, le=1)
    reason: str


def _rolled_segments(
    left: EditSegment,
    right: EditSegment,
    delta: float,
) -> tuple[EditSegment, EditSegment]:
    rolled_left = deepcopy(left)
    rolled_right = deepcopy(right)
    rolled_left.timeline_out_seconds += delta
    rolled_left.source_out_seconds += delta
    rolled_right.timeline_in_seconds += delta
    rolled_right.source_in_seconds += delta
    return rolled_left, rolled_right


def _anchor_candidates(
    segment: EditSegment,
    shot: ShotAnalysis,
    *,
    edge: str,
    anchor_types: set[str],
    max_shift_seconds: float,
    min_anchor_confidence: float,
):
    edge_time = segment.source_out_seconds if edge == "out" else segment.source_in_seconds
    return [
        (anchor, anchor.time_seconds - edge_time)
        for anchor in shot.edit_anchors
        if anchor.type in anchor_types
        and anchor.confidence >= min_anchor_confidence
        and abs(anchor.time_seconds - edge_time) <= max_shift_seconds
    ]


def propose_motion_match_boundary_roll(
    edit: EditPlan,
    vir: VirProject,
    boundary_index: int,
    *,
    max_shift_seconds: float = 0.35,
    min_anchor_confidence: float = 0.80,
    max_anchor_delta_difference: float = 0.10,
    minimum_phase_gain: float = 0.40,
    min_segment_duration: float = 0.60,
) -> MotionMatchBoundaryRoll | None:
    if boundary_index < 1 or boundary_index >= len(edit.segments):
        return None

    # Slip realignment is less invasive because timeline durations remain untouched.
    # Boundary roll is a fallback only when the safe slip primitive cannot solve timing.
    if propose_motion_match_realign(edit, vir, boundary_index) is not None:
        return None

    left = edit.segments[boundary_index - 1]
    right = edit.segments[boundary_index]
    shots = {shot.id: shot for shot in vir.shots}
    left_shot = shots.get(left.shot_id)
    right_shot = shots.get(right.shot_id)
    if left_shot is None or right_shot is None:
        return None

    before = build_cut_signature(left, right, left_shot, right_shot)
    if before.phase_compatibility >= 0.60:
        return None

    left_candidates = _anchor_candidates(
        left,
        left_shot,
        edge="out",
        anchor_types={"motion_peak"},
        max_shift_seconds=max_shift_seconds,
        min_anchor_confidence=min_anchor_confidence,
    )
    right_candidates = _anchor_candidates(
        right,
        right_shot,
        edge="in",
        anchor_types={"motion_onset", "motion_peak"},
        max_shift_seconds=max_shift_seconds,
        min_anchor_confidence=min_anchor_confidence,
    )
    if not left_candidates or not right_candidates:
        return None

    proposals: list[tuple[float, object, object, EditSegment, EditSegment, float]] = []
    for left_anchor, left_delta in left_candidates:
        for right_anchor, right_delta in right_candidates:
            if abs(left_delta - right_delta) > max_anchor_delta_difference:
                continue
            delta = (left_delta + right_delta) / 2.0
            if abs(delta) > max_shift_seconds:
                continue

            rolled_left, rolled_right = _rolled_segments(left, right, delta)
            left_duration = rolled_left.timeline_out_seconds - rolled_left.timeline_in_seconds
            right_duration = rolled_right.timeline_out_seconds - rolled_right.timeline_in_seconds
            if left_duration < min_segment_duration or right_duration < min_segment_duration:
                continue
            if rolled_left.source_out_seconds > left_shot.range.end_seconds + 1e-6:
                continue
            if rolled_left.source_out_seconds <= rolled_left.source_in_seconds + 1e-6:
                continue
            if rolled_right.source_in_seconds < right_shot.range.start_seconds - 1e-6:
                continue
            if rolled_right.source_in_seconds >= rolled_right.source_out_seconds - 1e-6:
                continue

            after = build_cut_signature(rolled_left, rolled_right, left_shot, right_shot)
            gain = after.phase_compatibility - before.phase_compatibility
            if after.phase_compatibility < 0.90 or gain < minimum_phase_gain:
                continue
            proposals.append((
                abs(left_delta - right_delta),
                left_anchor,
                right_anchor,
                rolled_left,
                rolled_right,
                delta,
            ))

    if not proposals:
        return None

    proposals.sort(key=lambda item: (item[0], abs(item[5])))
    _, left_anchor, right_anchor, rolled_left, rolled_right, delta = proposals[0]
    after = build_cut_signature(rolled_left, rolled_right, left_shot, right_shot)

    return MotionMatchBoundaryRoll(
        boundary_index=boundary_index,
        feasible=True,
        left_segment_id=left.id,
        right_segment_id=right.id,
        boundary_shift_seconds=delta,
        before_phase_compatibility=before.phase_compatibility,
        after_phase_compatibility=after.phase_compatibility,
        left_anchor_type=left_anchor.type,
        right_anchor_type=right_anchor.type,
        left_anchor_confidence=left_anchor.confidence,
        right_anchor_confidence=right_anchor.confidence,
        reason=(
            "A bounded roll edit can move the timeline boundary toward compatible outgoing/incoming motion anchors "
            "while preserving total sequence duration. The less-invasive slip realignment was not feasible."
        ),
    )


def apply_motion_match_boundary_roll(edit: EditPlan, proposal: MotionMatchBoundaryRoll) -> None:
    left = edit.segments[proposal.boundary_index - 1]
    right = edit.segments[proposal.boundary_index]
    if left.id != proposal.left_segment_id or right.id != proposal.right_segment_id:
        raise ValueError("Motion-match boundary-roll proposal no longer matches the edit boundary")

    delta = proposal.boundary_shift_seconds
    left.timeline_out_seconds += delta
    left.source_out_seconds += delta
    right.timeline_in_seconds += delta
    right.source_in_seconds += delta
    left.reason = f"{left.reason} Boundary rolled {delta:+.3f}s toward outgoing motion phase."
    right.reason = f"{right.reason} Boundary rolled {delta:+.3f}s toward incoming motion phase."
