from __future__ import annotations

from .advanced_analysis_models import (
    AdvancedAnalysisPlan,
    BoundaryAnalysisRequest,
    SegmentationPromptContext,
    SkippedBoundary,
    SourceAnalysisWindow,
)
from .analysis_models import OcclusionCueSample
from .ctl_models import CtlProgram
from .transition_opportunities import BoundaryTransitionOpportunity, TransitionOpportunityReport

OCCLUSION_SEGMENTATION_THRESHOLD = 0.58


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


def _prompt_from_seed(
    seed: OcclusionCueSample | None,
    side: str,
) -> SegmentationPromptContext | None:
    if seed is None or seed.score < OCCLUSION_SEGMENTATION_THRESHOLD:
        return None
    bbox = seed.largest_component_bbox_xywh_norm
    centroid = seed.largest_component_centroid_xy_norm
    if bbox is None or centroid is None:
        return None
    x, y, width, height = bbox
    if width <= 0 or height <= 0:
        return None
    return SegmentationPromptContext(
        side=side,  # type: ignore[arg-type]
        source_time_seconds=seed.time_seconds,
        point_xy_norm=list(centroid),
        box_xyxy_norm=[
            x,
            y,
            min(1.0, x + width),
            min(1.0, y + height),
        ],
        confidence=seed.score,
        occlusion_score=seed.score,
        dominant_edge=seed.dominant_edge,
    )


def _segmentation_prompt_contexts(
    boundary: BoundaryTransitionOpportunity,
) -> tuple[SegmentationPromptContext | None, SegmentationPromptContext | None]:
    left_prompt = _prompt_from_seed(boundary.outgoing_occlusion_seed, "left")
    right_prompt = _prompt_from_seed(boundary.incoming_occlusion_seed, "right")
    return left_prompt, right_prompt


def _segmentation_motivated(boundary: BoundaryTransitionOpportunity) -> bool:
    left_prompt, right_prompt = _segmentation_prompt_contexts(boundary)
    return left_prompt is not None or right_prompt is not None


def _features_with_segmentation(
    base: list[str],
    boundary: BoundaryTransitionOpportunity,
) -> list[str]:
    features = list(base)
    if _segmentation_motivated(boundary) and "segmentation" not in features:
        features.append("segmentation")
    return features


def _reason_with_segmentation(
    reason: str,
    boundary: BoundaryTransitionOpportunity,
) -> str:
    if not _segmentation_motivated(boundary):
        return reason
    left_prompt, right_prompt = _segmentation_prompt_contexts(boundary)
    prompted_sides = [
        side
        for side, prompt in (("outgoing", left_prompt), ("incoming", right_prompt))
        if prompt is not None
    ]
    return (
        f"{reason} Cheap camera-compensated occlusion evidence scores "
        f"{boundary.occlusion_candidate_score:.2f}; validated residual-component geometry exists on "
        f"{', '.join(prompted_sides)}, so segmentation is selectively requested only for those side(s)."
    )


def _request_for_boundary(
    ctl: CtlProgram,
    boundary: BoundaryTransitionOpportunity,
    *,
    force_action_verification: bool = False,
) -> BoundaryAnalysisRequest | None:
    candidate = _candidate(boundary)
    if candidate is None or not candidate.feasible:
        return None

    signature = boundary.cut_signature
    left_window, right_window, left_clip, right_clip = _windows(ctl, boundary)
    left_prompt, right_prompt = _segmentation_prompt_contexts(boundary)
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
        "occlusionCandidateScore": boundary.occlusion_candidate_score,
        "occlusionSide": boundary.occlusion_side,
        "occlusionEdge": boundary.occlusion_edge,
        "leftSegmentationPrompt": left_prompt is not None,
        "rightSegmentationPrompt": right_prompt is not None,
    }

    request_kwargs = {
        "left_segmentation_prompt": left_prompt,
        "right_segmentation_prompt": right_prompt,
    }

    if boundary.recommended_mechanism == "zoom_bridge":
        priority = min(1.0, 0.55 * candidate.motivation_score + 0.30 * candidate.feasibility_score + 0.15 * signature.global_motion_confidence)
        return BoundaryAnalysisRequest(
            boundary_index=boundary.boundary_index,
            priority=priority,
            requested_features=_features_with_segmentation(["dense_flow", "depth"], boundary),
            left_window=left_window,
            right_window=right_window,
            reason=_reason_with_segmentation(
                "A feasible zoom relation needs dense local motion plus selective depth before a 2.5D/scale bridge can be compiled safely.",
                boundary,
            ),
            evidence=evidence,
            **request_kwargs,
        )

    if boundary.recommended_mechanism == "directional_bridge":
        borderline = signature.relation_score < 0.75 or signature.global_motion_confidence < 0.65
        if borderline:
            priority = min(1.0, 0.50 * candidate.motivation_score + 0.30 * candidate.feasibility_score + 0.20 * (1.0 - signature.global_motion_confidence))
            return BoundaryAnalysisRequest(
                boundary_index=boundary.boundary_index,
                priority=priority,
                requested_features=_features_with_segmentation(["dense_flow"], boundary),
                left_window=left_window,
                right_window=right_window,
                reason=_reason_with_segmentation(
                    "The directional bridge is feasible but global-motion evidence is borderline; dense flow is budgeted only around this boundary for validation.",
                    boundary,
                ),
                evidence=evidence,
                **request_kwargs,
            )

    if boundary.recommended_mechanism == "action_cut" and (
        force_action_verification or 0.6 <= signature.phase_compatibility < 0.9
    ):
        evidence["forcedRevisionVerification"] = force_action_verification
        priority = 1.0 if force_action_verification else min(
            1.0,
            0.45 + 0.35 * candidate.motivation_score + 0.20 * candidate.feasibility_score,
        )
        base_reason = (
            "A post-render timing revision changed this action boundary; dense flow is mandatory to verify the revised cut location before candidate promotion."
            if force_action_verification
            else "The cheap motion-phase signal supports cut-on-action but is not decisive; dense flow can refine the event timing inside a narrow boundary window."
        )
        return BoundaryAnalysisRequest(
            boundary_index=boundary.boundary_index,
            priority=priority,
            requested_features=_features_with_segmentation(["dense_flow"], boundary),
            left_window=left_window,
            right_window=right_window,
            reason=_reason_with_segmentation(base_reason, boundary),
            evidence=evidence,
            **request_kwargs,
        )

    if _segmentation_motivated(boundary):
        priority = min(1.0, 0.45 + 0.50 * boundary.occlusion_candidate_score)
        return BoundaryAnalysisRequest(
            boundary_index=boundary.boundary_index,
            priority=priority,
            requested_features=["segmentation"],
            left_window=left_window,
            right_window=right_window,
            reason=_reason_with_segmentation(
                "No additional dense-flow/depth refinement is justified by the current transition mechanism.",
                boundary,
            ),
            evidence=evidence,
            **request_kwargs,
        )

    return None


def build_advanced_analysis_plan(
    ctl: CtlProgram,
    opportunities: TransitionOpportunityReport,
    max_boundaries: int = 4,
    forced_action_boundaries: set[int] | None = None,
) -> AdvancedAnalysisPlan:
    if ctl.project_id != opportunities.project_id:
        raise ValueError("CTL projectId does not match transition opportunity report")
    if max_boundaries < 1:
        raise ValueError("max_boundaries must be >= 1")

    forced = set(forced_action_boundaries or set())
    forced_requests: list[BoundaryAnalysisRequest] = []
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

        is_forced = boundary.boundary_index in forced
        request = _request_for_boundary(
            ctl,
            boundary,
            force_action_verification=is_forced,
        )
        if request is None:
            skipped.append(SkippedBoundary(
                boundary_index=boundary.boundary_index,
                reason=(
                    "Mandatory action-timing verification could not be scheduled because the revised boundary is no longer a feasible action-cut opportunity."
                    if is_forced
                    else "Cheap VIR/CutSignature/occlusion evidence is sufficient for the current decision; no expensive boundary analysis is justified."
                ),
            ))
        elif is_forced:
            forced_requests.append(request)
        else:
            candidates.append(request)

    forced_requests.sort(key=lambda request: request.boundary_index)
    candidates.sort(key=lambda request: (-request.priority, request.boundary_index))
    remaining_budget = max(0, max_boundaries - len(forced_requests))
    selected = forced_requests + candidates[:remaining_budget]
    for request in candidates[remaining_budget:]:
        skipped.append(SkippedBoundary(
            boundary_index=request.boundary_index,
            reason=f"Eligible for {', '.join(request.requested_features)} but deferred by the max_boundaries={max_boundaries} compute budget.",
        ))

    effective_budget = max(max_boundaries, len(forced_requests))
    return AdvancedAnalysisPlan(
        project_id=ctl.project_id,
        max_boundaries=effective_budget,
        requests=selected,
        skipped_boundaries=sorted(skipped, key=lambda item: item.boundary_index),
        notes=[
            "This plan schedules expensive analysis only; it does not execute model backends.",
            "Segmentation is requested only when cheap camera-compensated foreground evidence crosses the threshold and the same residual component provides valid normalized prompt geometry.",
            "Segmentation prompt contexts preserve source time, point, box, confidence, edge, and provenance independently from any concrete model API.",
            "Depth is currently requested only for feasible zoom-bridge opportunities.",
            "Dense flow is limited to ambiguous action/directional boundaries, depth-assisted zoom candidates, or mandatory post-revision verification.",
            "Post-render action-timing revision boundaries are forced into dense-flow verification even when cheap phase evidence becomes near-certain; mandatory verification may consume the configured budget before optional boundaries.",
        ],
    )
