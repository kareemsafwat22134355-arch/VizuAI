from __future__ import annotations

from typing import Literal

from pydantic import Field

from .analysis_models import OcclusionCueSample, OcclusionEdge, ShotAnalysis, VirProject
from .cut_signature import CutSignature, build_cut_signature
from .models import PortableModel
from .planning_models import EditPlan, EditSegment

TransitionOpportunityMechanism = Literal[
    "hard_cut",
    "action_cut",
    "directional_bridge",
    "zoom_bridge",
]
OcclusionBoundarySide = Literal["none", "outgoing", "incoming", "both"]


class TransitionCandidate(PortableModel):
    mechanism: TransitionOpportunityMechanism
    duration_seconds: float = Field(ge=0, le=1)
    required_handle_seconds: float = Field(ge=0, le=1)
    feasible: bool
    feasibility_score: float = Field(ge=0, le=1)
    motivation_score: float = Field(ge=0, le=1)
    relation_score: float = Field(ge=0, le=1)
    parameters: dict[str, float | str | bool] = Field(default_factory=dict)
    reason: str


class BoundaryTransitionOpportunity(PortableModel):
    boundary_index: int = Field(ge=1)
    left_segment_id: str
    right_segment_id: str
    outgoing_handle_seconds: float = Field(ge=0)
    incoming_handle_seconds: float = Field(ge=0)
    cut_signature: CutSignature
    recommended_mechanism: TransitionOpportunityMechanism
    candidates: list[TransitionCandidate]
    occlusion_candidate_score: float = Field(default=0.0, ge=0, le=1)
    occlusion_side: OcclusionBoundarySide = "none"
    occlusion_edge: OcclusionEdge = "none"
    outgoing_occlusion_seed: OcclusionCueSample | None = None
    incoming_occlusion_seed: OcclusionCueSample | None = None


class TransitionOpportunityReport(PortableModel):
    project_id: str
    boundaries: list[BoundaryTransitionOpportunity]
    notes: list[str] = Field(default_factory=list)


def _available_handles(
    left_segment: EditSegment,
    right_segment: EditSegment,
    left_shot: ShotAnalysis,
    right_shot: ShotAnalysis,
) -> tuple[float, float]:
    outgoing = max(0.0, left_shot.range.end_seconds - left_segment.source_out_seconds)
    incoming = max(0.0, right_segment.source_in_seconds - right_shot.range.start_seconds)
    return outgoing, incoming


def _bridge_feasibility(outgoing: float, incoming: float, required: float) -> tuple[bool, float]:
    if required <= 0:
        return True, 1.0
    score = min(1.0, outgoing / required, incoming / required)
    return outgoing >= required and incoming >= required, max(0.0, score)


def _near_occlusion_sample(
    shot: ShotAnalysis,
    time_seconds: float,
    radius_seconds: float = 0.45,
) -> OcclusionCueSample | None:
    candidates = [
        sample
        for sample in shot.occlusion.samples
        if abs(sample.time_seconds - time_seconds) <= radius_seconds
    ]
    return max(candidates, key=lambda sample: sample.score) if candidates else None


def _boundary_occlusion_evidence(
    left_segment: EditSegment,
    right_segment: EditSegment,
    left_shot: ShotAnalysis,
    right_shot: ShotAnalysis,
    meaningful_threshold: float = 0.52,
) -> tuple[
    float,
    OcclusionBoundarySide,
    OcclusionEdge,
    OcclusionCueSample | None,
    OcclusionCueSample | None,
]:
    outgoing = _near_occlusion_sample(left_shot, left_segment.source_out_seconds)
    incoming = _near_occlusion_sample(right_shot, right_segment.source_in_seconds)
    outgoing_score = outgoing.score if outgoing is not None else 0.0
    incoming_score = incoming.score if incoming is not None else 0.0
    score = max(outgoing_score, incoming_score)

    outgoing_meaningful = outgoing_score >= meaningful_threshold
    incoming_meaningful = incoming_score >= meaningful_threshold
    if outgoing_meaningful and incoming_meaningful:
        side: OcclusionBoundarySide = "both"
        if outgoing is not None and incoming is not None and outgoing.dominant_edge == incoming.dominant_edge:
            edge = outgoing.dominant_edge
        else:
            edge = "mixed"
    elif outgoing_meaningful:
        side = "outgoing"
        edge = outgoing.dominant_edge if outgoing is not None else "none"
    elif incoming_meaningful:
        side = "incoming"
        edge = incoming.dominant_edge if incoming is not None else "none"
    else:
        side = "none"
        edge = "none"

    return score, side, edge, outgoing, incoming


def _hard_cut_candidate(signature: CutSignature) -> TransitionCandidate:
    motivation = max(0.45, 0.9 - 0.45 * signature.relation_score)
    return TransitionCandidate(
        mechanism="hard_cut",
        duration_seconds=0.0,
        required_handle_seconds=0.0,
        feasible=True,
        feasibility_score=1.0,
        motivation_score=motivation,
        relation_score=signature.relation_score,
        reason="Always-valid fallback. Preserve the discontinuity when stronger bridge evidence is absent or handles are insufficient.",
    )


def _action_cut_candidate(signature: CutSignature) -> TransitionCandidate:
    motivated = signature.phase_compatibility >= 0.6
    motivation = 0.35 + 0.6 * signature.phase_compatibility
    return TransitionCandidate(
        mechanism="action_cut",
        duration_seconds=0.0,
        required_handle_seconds=0.0,
        feasible=motivated,
        feasibility_score=1.0 if motivated else 0.0,
        motivation_score=max(0.0, min(1.0, motivation)),
        relation_score=signature.relation_score,
        reason=(
            "A measured motion phase supports a zero-duration cut-on-action boundary."
            if motivated
            else "Motion-phase evidence is too weak to label this as a cut-on-action opportunity."
        ),
    )


def _directional_bridge_candidate(
    signature: CutSignature,
    left_shot: ShotAnalysis,
    right_shot: ShotAnalysis,
    outgoing_handle: float,
    incoming_handle: float,
) -> TransitionCandidate:
    required = 0.08
    handle_feasible, handle_score = _bridge_feasibility(outgoing_handle, incoming_handle, required)
    evidence_feasible = (
        signature.direction_compatibility >= 0.9
        and signature.global_motion_confidence >= 0.35
        and signature.relation_score >= 0.55
    )
    feasible = handle_feasible and evidence_feasible
    motivation = (
        0.50 * signature.direction_compatibility
        + 0.30 * signature.relation_score
        + 0.20 * signature.global_motion_confidence
    )
    direction = left_shot.global_motion.dominant_screen_direction
    return TransitionCandidate(
        mechanism="directional_bridge",
        duration_seconds=0.12,
        required_handle_seconds=required,
        feasible=feasible,
        feasibility_score=handle_score if evidence_feasible else 0.0,
        motivation_score=max(0.0, min(1.0, motivation)),
        relation_score=signature.relation_score,
        parameters={
            "screenDirection": direction,
            "leftDirection": left_shot.global_motion.dominant_screen_direction,
            "rightDirection": right_shot.global_motion.dominant_screen_direction,
        },
        reason=(
            "Matched global screen direction plus usable source handles can support a short directional bridge."
            if feasible
            else "Directional evidence or source handles are insufficient; do not force a spatial bridge."
        ),
    )


def _zoom_bridge_candidate(
    signature: CutSignature,
    left_shot: ShotAnalysis,
    right_shot: ShotAnalysis,
    outgoing_handle: float,
    incoming_handle: float,
) -> TransitionCandidate:
    required = 0.10
    handle_feasible, handle_score = _bridge_feasibility(outgoing_handle, incoming_handle, required)
    left_zoom = left_shot.global_motion.zoom_direction
    right_zoom = right_shot.global_motion.zoom_direction
    evidence_feasible = (
        signature.zoom_compatibility >= 0.9
        and left_zoom in {"in", "out"}
        and right_zoom == left_zoom
        and signature.global_motion_confidence >= 0.35
    )
    feasible = handle_feasible and evidence_feasible
    motivation = 0.55 * signature.zoom_compatibility + 0.25 * signature.relation_score + 0.20 * signature.global_motion_confidence
    return TransitionCandidate(
        mechanism="zoom_bridge",
        duration_seconds=0.14,
        required_handle_seconds=required,
        feasible=feasible,
        feasibility_score=handle_score if evidence_feasible else 0.0,
        motivation_score=max(0.0, min(1.0, motivation)),
        relation_score=signature.relation_score,
        parameters={"zoomDirection": left_zoom},
        reason=(
            "Both shots share a confident zoom direction and have enough handles for a short scale bridge."
            if feasible
            else "Zoom relation or source handles are insufficient; preserve a simpler boundary."
        ),
    )


def _recommend(candidates: list[TransitionCandidate]) -> TransitionOpportunityMechanism:
    feasible = [candidate for candidate in candidates if candidate.feasible]
    if not feasible:
        return "hard_cut"

    def score(candidate: TransitionCandidate) -> float:
        penalty = 0.08 if candidate.duration_seconds > 0 else 0.0
        return candidate.motivation_score * candidate.feasibility_score - penalty

    return max(feasible, key=score).mechanism


def synthesize_transition_opportunities(edit_plan: EditPlan, vir: VirProject) -> TransitionOpportunityReport:
    shots = {shot.id: shot for shot in vir.shots}
    boundaries: list[BoundaryTransitionOpportunity] = []

    for boundary_index, (left_segment, right_segment) in enumerate(
        zip(edit_plan.segments, edit_plan.segments[1:]),
        start=1,
    ):
        left_shot = shots.get(left_segment.shot_id)
        right_shot = shots.get(right_segment.shot_id)
        if left_shot is None or right_shot is None:
            continue

        signature = build_cut_signature(left_segment, right_segment, left_shot, right_shot)
        outgoing_handle, incoming_handle = _available_handles(left_segment, right_segment, left_shot, right_shot)
        (
            occlusion_score,
            occlusion_side,
            occlusion_edge,
            outgoing_occlusion_seed,
            incoming_occlusion_seed,
        ) = _boundary_occlusion_evidence(
            left_segment,
            right_segment,
            left_shot,
            right_shot,
        )
        candidates = [
            _hard_cut_candidate(signature),
            _action_cut_candidate(signature),
            _directional_bridge_candidate(signature, left_shot, right_shot, outgoing_handle, incoming_handle),
            _zoom_bridge_candidate(signature, left_shot, right_shot, outgoing_handle, incoming_handle),
        ]
        boundaries.append(
            BoundaryTransitionOpportunity(
                boundary_index=boundary_index,
                left_segment_id=left_segment.id,
                right_segment_id=right_segment.id,
                outgoing_handle_seconds=outgoing_handle,
                incoming_handle_seconds=incoming_handle,
                cut_signature=signature,
                recommended_mechanism=_recommend(candidates),
                candidates=candidates,
                occlusion_candidate_score=occlusion_score,
                occlusion_side=occlusion_side,
                occlusion_edge=occlusion_edge,
                outgoing_occlusion_seed=outgoing_occlusion_seed,
                incoming_occlusion_seed=incoming_occlusion_seed,
            )
        )

    return TransitionOpportunityReport(
        project_id=edit_plan.project_id,
        boundaries=boundaries,
        notes=[
            "This report scores transition opportunities independently from CTL compilation; CTL v0.2 can promote supported feasible candidates such as directional_bridge.",
            "Hard cuts remain first-class valid decisions at every boundary.",
            "Non-zero bridge candidates require both physical motivation and verified source handles on each side of the cut.",
            "Cheap camera-compensated occlusion likelihood is boundary evidence only; exact near-cut cue samples are preserved for later prompt derivation but do not claim a segmentation mask exists.",
            "Unsupported primitives or candidates adjacent to event-driven timewarps remain opportunities and fall back safely during CTL compilation.",
        ],
    )
