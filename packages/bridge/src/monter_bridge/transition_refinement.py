from __future__ import annotations

from .advanced_execution_models import AdvancedAnalysisResults, BoundaryExecutionResult
from .transition_opportunities import TransitionOpportunityReport
from .transition_refinement_models import BoundaryTransitionRefinement, TransitionRefinementReport

CONFIRM_FLOW_COMPATIBILITY = 0.72
DEMOTE_FLOW_COMPATIBILITY = 0.35
MIN_DIRECTIONAL_COHERENCE = 0.20

CONFIRM_ACTION_OFFSET_SECONDS = 0.16
DEMOTE_ACTION_DELTA_DISAGREEMENT_SECONDS = 0.28
MAX_REPAIRABLE_ACTION_SHIFT_SECONDS = 0.45
MIN_ACTION_TEMPORAL_CONTRAST = 1.05
MIN_ACTION_FLOW_SAMPLES = 2


def _dense_feature(executed: BoundaryExecutionResult):
    return next((feature for feature in executed.features if feature.feature == "dense_flow"), None)


def _action_refinement(boundary, executed: BoundaryExecutionResult | None) -> BoundaryTransitionRefinement:
    base = boundary.recommended_mechanism
    if executed is None:
        return BoundaryTransitionRefinement(
            boundary_index=boundary.boundary_index,
            base_mechanism=base,
            refined_mechanism=base,
            status="unresolved",
            reason="No advanced execution result exists for this action-cut boundary; preserve the base recommendation.",
        )

    dense_flow = _dense_feature(executed)
    left = executed.left_flow
    right = executed.right_flow
    if dense_flow is None or dense_flow.status != "completed" or left is None or right is None:
        return BoundaryTransitionRefinement(
            boundary_index=boundary.boundary_index,
            base_mechanism=base,
            refined_mechanism=base,
            status="unresolved",
            reason="Dense-flow action timing was requested but did not complete on both sides of the boundary.",
        )

    left_cut = executed.request_evidence.get("leftSourceOutSeconds")
    right_cut = executed.request_evidence.get("rightSourceInSeconds")
    left_peak = left.peak_time_seconds
    right_event = right.onset_time_seconds if right.onset_time_seconds is not None else right.peak_time_seconds

    evidence: dict[str, float | str | bool] = {
        "basePhaseCompatibility": boundary.cut_signature.phase_compatibility,
        "leftTemporalContrast": left.temporal_contrast,
        "rightTemporalContrast": right.temporal_contrast,
        "leftPeakMagnitude": left.peak_magnitude,
        "rightPeakMagnitude": right.peak_magnitude,
        "leftFlowSamples": left.sample_count,
        "rightFlowSamples": right.sample_count,
    }
    if left_peak is not None:
        evidence["leftPeakTimeSeconds"] = left_peak
    if right.onset_time_seconds is not None:
        evidence["rightOnsetTimeSeconds"] = right.onset_time_seconds
    if right.peak_time_seconds is not None:
        evidence["rightPeakTimeSeconds"] = right.peak_time_seconds

    if not isinstance(left_cut, (int, float)) or not isinstance(right_cut, (int, float)):
        return BoundaryTransitionRefinement(
            boundary_index=boundary.boundary_index,
            base_mechanism=base,
            refined_mechanism=base,
            status="unresolved",
            reason="Dense flow completed, but the advanced request did not preserve source cut times needed for action timing.",
            evidence=evidence,
        )
    if left_peak is None or right_event is None:
        return BoundaryTransitionRefinement(
            boundary_index=boundary.boundary_index,
            base_mechanism=base,
            refined_mechanism=base,
            status="unresolved",
            reason="Dense flow completed, but a temporal motion event could not be localized on both sides of the cut.",
            evidence=evidence,
        )

    left_offset = float(left_peak - float(left_cut))
    right_offset = float(right_event - float(right_cut))
    disagreement = abs(left_offset - right_offset)
    max_offset = max(abs(left_offset), abs(right_offset))
    mean_shift = (left_offset + right_offset) / 2.0
    evidence.update({
        "leftActionOffsetSeconds": left_offset,
        "rightActionOffsetSeconds": right_offset,
        "actionOffsetDisagreementSeconds": disagreement,
        "suggestedBoundaryShiftSeconds": mean_shift,
    })

    reliable = (
        left.sample_count >= MIN_ACTION_FLOW_SAMPLES
        and right.sample_count >= MIN_ACTION_FLOW_SAMPLES
        and min(left.temporal_contrast, right.temporal_contrast) >= MIN_ACTION_TEMPORAL_CONTRAST
        and left.peak_magnitude > 1e-6
        and right.peak_magnitude > 1e-6
    )
    if not reliable:
        return BoundaryTransitionRefinement(
            boundary_index=boundary.boundary_index,
            base_mechanism=base,
            refined_mechanism=base,
            status="unresolved",
            reason="Temporal dense flow is too flat or undersampled to overrule the cheaper action-phase evidence.",
            evidence=evidence,
        )

    if max_offset <= CONFIRM_ACTION_OFFSET_SECONDS:
        return BoundaryTransitionRefinement(
            boundary_index=boundary.boundary_index,
            base_mechanism=base,
            refined_mechanism="action_cut",
            status="confirmed",
            reason="Selective dense flow localizes the outgoing peak and incoming onset/peak close to the current cut, confirming cut-on-action timing.",
            evidence=evidence,
        )

    if disagreement >= DEMOTE_ACTION_DELTA_DISAGREEMENT_SECONDS:
        return BoundaryTransitionRefinement(
            boundary_index=boundary.boundary_index,
            base_mechanism=base,
            refined_mechanism="hard_cut",
            status="demoted",
            reason=(
                "Dense-flow temporal events disagree on where a shared action cut should land; "
                "demote to a deliberate hard cut instead of forcing false continuity."
            ),
            evidence=evidence,
        )

    if max_offset <= MAX_REPAIRABLE_ACTION_SHIFT_SECONDS:
        return BoundaryTransitionRefinement(
            boundary_index=boundary.boundary_index,
            base_mechanism=base,
            refined_mechanism=base,
            status="unchanged",
            reason=(
                "Dense flow supports a common local timing shift but not the current cut position; "
                "preserve the action-cut intent and expose the suggested boundary shift for a deterministic revision layer."
            ),
            evidence=evidence,
        )

    return BoundaryTransitionRefinement(
        boundary_index=boundary.boundary_index,
        base_mechanism=base,
        refined_mechanism=base,
        status="unresolved",
        reason="Localized motion events are too far from the current boundary for the bounded timing-repair window.",
        evidence=evidence,
    )


def refine_transition_opportunities(
    opportunities: TransitionOpportunityReport,
    results: AdvancedAnalysisResults,
) -> TransitionRefinementReport:
    if opportunities.project_id != results.project_id:
        raise ValueError("Transition opportunity report projectId does not match advanced analysis results")

    results_by_boundary = {boundary.boundary_index: boundary for boundary in results.boundaries}
    refinements: list[BoundaryTransitionRefinement] = []

    for boundary in opportunities.boundaries:
        base = boundary.recommended_mechanism
        executed = results_by_boundary.get(boundary.boundary_index)

        if base == "action_cut":
            refinements.append(_action_refinement(boundary, executed))
            continue

        if base != "directional_bridge":
            refinements.append(BoundaryTransitionRefinement(
                boundary_index=boundary.boundary_index,
                base_mechanism=base,
                refined_mechanism=base,
                status="unchanged",
                reason="Selective dense-flow timing refinement is currently defined for action cuts and directional bridges only; preserve the base mechanism.",
            ))
            continue

        if executed is None:
            refinements.append(BoundaryTransitionRefinement(
                boundary_index=boundary.boundary_index,
                base_mechanism=base,
                refined_mechanism=base,
                status="unresolved",
                reason="No advanced execution result exists for this directional-bridge boundary; preserve the base recommendation.",
            ))
            continue

        dense_flow = _dense_feature(executed)
        compatibility = executed.flow_direction_compatibility
        left_coherence = executed.left_flow.directional_coherence if executed.left_flow else None
        right_coherence = executed.right_flow.directional_coherence if executed.right_flow else None

        evidence = {
            "baseRelationScore": boundary.cut_signature.relation_score,
            "baseDirectionCompatibility": boundary.cut_signature.direction_compatibility,
            "baseGlobalMotionConfidence": boundary.cut_signature.global_motion_confidence,
        }
        if compatibility is not None:
            evidence["flowDirectionCompatibility"] = compatibility
        if left_coherence is not None:
            evidence["leftDirectionalCoherence"] = left_coherence
        if right_coherence is not None:
            evidence["rightDirectionalCoherence"] = right_coherence

        if dense_flow is None or dense_flow.status != "completed" or compatibility is None:
            refinements.append(BoundaryTransitionRefinement(
                boundary_index=boundary.boundary_index,
                base_mechanism=base,
                refined_mechanism=base,
                status="unresolved",
                reason="Dense-flow refinement was requested but did not complete; preserve the base directional recommendation instead of guessing.",
                flow_direction_compatibility=compatibility,
                left_directional_coherence=left_coherence,
                right_directional_coherence=right_coherence,
                evidence=evidence,
            ))
            continue

        min_coherence = min(left_coherence or 0.0, right_coherence or 0.0)
        if min_coherence < MIN_DIRECTIONAL_COHERENCE:
            refinements.append(BoundaryTransitionRefinement(
                boundary_index=boundary.boundary_index,
                base_mechanism=base,
                refined_mechanism=base,
                status="unresolved",
                reason="Dense flow completed, but directional coherence is too weak to overrule the cheaper global-motion evidence.",
                flow_direction_compatibility=compatibility,
                left_directional_coherence=left_coherence,
                right_directional_coherence=right_coherence,
                evidence=evidence,
            ))
            continue

        if compatibility >= CONFIRM_FLOW_COMPATIBILITY:
            refinements.append(BoundaryTransitionRefinement(
                boundary_index=boundary.boundary_index,
                base_mechanism=base,
                refined_mechanism="directional_bridge",
                status="confirmed",
                reason="Selective dense flow confirms that outgoing and incoming motion vectors remain directionally compatible around the edit boundary.",
                flow_direction_compatibility=compatibility,
                left_directional_coherence=left_coherence,
                right_directional_coherence=right_coherence,
                evidence=evidence,
            ))
            continue

        if compatibility <= DEMOTE_FLOW_COMPATIBILITY:
            fallback = "action_cut" if boundary.cut_signature.phase_compatibility >= 0.6 else "hard_cut"
            refinements.append(BoundaryTransitionRefinement(
                boundary_index=boundary.boundary_index,
                base_mechanism=base,
                refined_mechanism=fallback,
                status="demoted",
                reason=(
                    "Selective dense flow contradicts the coarse global-motion match; demote the directional bridge "
                    "to the strongest zero-duration boundary supported by existing phase evidence."
                ),
                flow_direction_compatibility=compatibility,
                left_directional_coherence=left_coherence,
                right_directional_coherence=right_coherence,
                evidence=evidence,
            ))
            continue

        refinements.append(BoundaryTransitionRefinement(
            boundary_index=boundary.boundary_index,
            base_mechanism=base,
            refined_mechanism=base,
            status="unchanged",
            reason="Dense flow is coherent but neither strongly confirms nor contradicts the directional bridge; keep the base recommendation.",
            flow_direction_compatibility=compatibility,
            left_directional_coherence=left_coherence,
            right_directional_coherence=right_coherence,
            evidence=evidence,
        ))

    return TransitionRefinementReport(
        project_id=opportunities.project_id,
        boundaries=refinements,
        notes=[
            "Selective dense flow can confirm/demote directional bridges and now localize action timing for ambiguous action cuts.",
            "Action timing evidence preserves outgoing peak / incoming onset-or-peak offsets relative to the source cut.",
            "A common bounded timing shift is exposed as suggestedBoundaryShiftSeconds instead of mutating the edit inside the refinement layer.",
            "Missing, failed, flat, or incoherent dense flow never overrules the cheaper base recommendation.",
        ],
    )
