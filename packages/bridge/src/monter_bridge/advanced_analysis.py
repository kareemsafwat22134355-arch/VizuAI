from __future__ import annotations

from .advanced_analysis_models import (
    AdvancedAnalysisPlan,
    BoundaryAnalysisRequest,
    SkippedBoundary,
    SourceAnalysisWindow,
)
from .ctl_models import CtlProgram
from .transition_opportunities import BoundaryTransitionOpportunity, TransitionOpportunityReport


def _candidate(boundary: BoundaryTransitionOpportunity):
    return next(
        (candidate for candidate in boundary.candidates if candidate.mechanism == boundary.recommended_mechanism),
        None,
    )


def _windows(ctl: CtlProgram, boundary: BoundaryTransitionOpportunity, radius: float = 0.35):
    left_index = boundary.boundary_index - 1
    right_index = boundary.boundary_index
    if left_index < 0 or right_index >= len(ctl.clips):
        raise ValueError(f"Boundary {boundary.boundary_index} is outside CTL clip range")
    left = ctl.clips[left_index]
    right = ctl.clips[right_index]

    # Stay inside the chosen source ranges except for handles already verified by
    # transition-opportunity synthesis. No advanced request may invent source time.
    left_after = min(boundary.outgoing_handle_seconds, radius)
    right_before = min(boundary.incoming_handle_seconds, radius)
    left_window = SourceAnalysisWindow(
        segment_id=left.id,
        asset_id=left.asset_id,
        shot_id=left.shot_id,
        source_start_seconds=max(left.source_in_seconds, left.source_out_seconds - radius),
        source_end_seconds=left.source_out_seconds + left_after,
    )
    right_window = SourceAnalysisWindow(
        segment_id=right.id,
        asset_id=right.asset_id,
        shot_id=right.shot_id,
        source_start_seconds=max(0.0, right.source_in_seconds - right_before),
        source_end_seconds=min(right.source_out_seconds, right.source_in_seconds + radius),
    )
    return left_window, right_window, left, right


def _request_for_boundary(
    ctl: CtlProgram,
    boundary: BoundaryTransitionOpportunity,
) -> BoundaryAnalysisRequest | None:
    candidate = _candidate(boundary)
    if candidate is None or not candidate.feasible:
        return None

    signature = boundary.cut_signature
    left_window, right_window, left_clip, right_clip = _windows(ctl, boundary)
    evidence: dict[str, float | str | bool] = {
        "recommendedMechanism": boundary.recommended_mechanism,
        "relationScore": signature.relation_score,
        "phaseCompatibility": signature.phase_compatibility,
        "directionCompatibility": signature.direction_compatibility,
        "zoomCompatibility": signature.zoom_compatibility,
        "globalMotionConfidence": signature.global_motion_confidence,
        "outgoingHandleSeconds": boundary.outgoing_handle_seconds,
        "incomingHandleSeconds": boundary.incoming_handle_seconds,
        "leftSourceOutSeconds": left_clip.source_out_seconds,
        "rightSourceInSeconds": right_clip.source_in_seconds,
    }

    # Depth is currently useful only where a scale relation already exists. It is
    # deliberately not scheduled across all media or all transitions.
    if boundary.recommended_mechanism == "zoom_bridge":
        priority = min(1.0, 0.55 * candidate.motivation_score + 0.30 * candidate.feasibility_score + 0.15 * signature.global_motion_confidence)
        return BoundaryAnalysisRequest(
            boundary_index=boundary.boundary_index,
            priority=priority,
            requested_features=["dense_flow", "depth"],
            left_window=left_window,
            right_window=right_window,
            reason="A feasible zoom relation needs dense local motion plus selective depth before a 2.5D/scale bridge can be compiled safely.",
            evidence=evidence,
        )

    # Borderline directional bridges benefit from dense local flow validation.
    # Very strong global-motion matches are intentionally left cheap.
    if boundary.recommended_mechanism == "directional_bridge":
        borderline = signature.relation_score < 0.75 or signature.global_motion_confidence < 0.65
        if not borderline:
            return None
        priority = min(1.0, 0.50 * candidate.motivation_score + 0.30 * candidate.feasibility_score + 0.20 * (1.0 - signature.global_motion_confidence))
        return BoundaryAnalysisRequest(
            boundary_index=boundary.boundary_index,
            priority=priority,
            requested_features=["dense_flow"],
            left_window=left_window,
            right_window=right_window,
            reason="The directional bridge is feasible but global-motion evidence is borderline; dense flow is budgeted only around this boundary for validation.",
            evidence=evidence,
        )

    # Action cuts only need expensive refinement when the cheap phase score is
    # plausible but not already near-certain.
    if boundary.recommended_mechanism == "action_cut" and 0.6 <= signature.phase_compatibility < 0.9:
        priority = min(1.0, 0.45 + 0.35 * candidate.motivation_score + 0.20 * candidate.feasibility_score)
        return BoundaryAnalysisRequest(
            boundary_index=boundary.boundary_index,
            priority=priority,
            requested_features=["dense_flow"],
            left_window=left_window,
            right_window=right_window,
            reason="The cheap motion-phase signal supports cut-on-action but is not decisive; dense flow can refine the event timing inside a narrow boundary window.",
            evidence=evidence,
        )

    return None


def build_advanced_analysis_plan(
    ctl: CtlProgram,
    opportunities: TransitionOpportunityReport,
    max_boundaries: int = 4,
) -> AdvancedAnalysisPlan:
    if ctl.project_id != opportunities.project_id:
        raise ValueError("CTL projectId does not match transition opportunity report")
    if max_boundaries < 1:
        raise ValueError("max_boundaries must be >= 1")

    candidates: list[BoundaryAnalysisRequest] = []
    skipped: list[SkippedBoundary] = []
    transition_by_boundary = {transition.boundary_index: transition for transition in ctl.transitions}

    for boundary in opportunities.boundaries:
        transition = transition_by_boundary.get(boundary.boundary_index)
        adjacent_timewarp = bool(transition and transition.evidence.get("adjacentTimewarp", False))
        if adjacent_timewarp:
            skipped.append(SkippedBoundary(
                boundary_index=boundary.boundary_index,
                reason="Skipped expensive transition analysis because an adjacent event-driven timewarp already owns the temporal transformation.",
            ))
            continue

        request = _request_for_boundary(ctl, boundary)
        if request is None:
            skipped.append(SkippedBoundary(
                boundary_index=boundary.boundary_index,
                reason="Cheap VIR/CutSignature evidence is sufficient for the current decision; no expensive boundary analysis is justified.",
            ))
        else:
            candidates.append(request)

    candidates.sort(key=lambda request: (-request.priority, request.boundary_index))
    selected = candidates[:max_boundaries]
    for request in candidates[max_boundaries:]:
        skipped.append(SkippedBoundary(
            boundary_index=request.boundary_index,
            reason=f"Eligible for {', '.join(request.requested_features)} but deferred by the max_boundaries={max_boundaries} compute budget.",
        ))

    return AdvancedAnalysisPlan(
        project_id=ctl.project_id,
        max_boundaries=max_boundaries,
        requests=selected,
        skipped_boundaries=sorted(skipped, key=lambda item: item.boundary_index),
        notes=[
            "This plan schedules expensive analysis only; it does not execute model backends.",
            "Segmentation is supported by the contract but is not scheduled until cheap subject/occlusion evidence exists.",
            "Depth is currently requested only for feasible zoom-bridge opportunities.",
            "Dense flow is limited to ambiguous action/directional boundaries or depth-assisted zoom candidates.",
        ],
    )
