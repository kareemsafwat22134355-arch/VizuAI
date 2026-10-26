from __future__ import annotations

from .advanced_execution_models import AdvancedAnalysisResults
from .transition_opportunities import TransitionOpportunityReport
from .transition_refinement_models import BoundaryTransitionRefinement, TransitionRefinementReport

CONFIRM_FLOW_COMPATIBILITY = 0.72
DEMOTE_FLOW_COMPATIBILITY = 0.35
MIN_DIRECTIONAL_COHERENCE = 0.20


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

        if base != "directional_bridge":
            refinements.append(BoundaryTransitionRefinement(
                boundary_index=boundary.boundary_index,
                base_mechanism=base,
                refined_mechanism=base,
                status="unchanged",
                reason="v0.18 uses dense-flow evidence only to verify or demote directional bridges; other mechanisms are preserved.",
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

        dense_flow = next((feature for feature in executed.features if feature.feature == "dense_flow"), None)
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
            "v0.18 allows executed dense flow to confirm or demote directional bridges only.",
            "Action timing, zoom depth, semantics, and segmentation are not inferred from these flow summaries.",
            "Missing, failed, or incoherent dense flow never overrules the cheaper base recommendation.",
        ],
    )
