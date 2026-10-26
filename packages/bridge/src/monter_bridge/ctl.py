from __future__ import annotations

from .analysis_models import VirProject
from .ctl_models import CtlClip, CtlProgram, CtlTransition
from .cut_signature import build_cut_signature
from .planning_models import EditPlan
from .timewarp import select_timewarp_intents
from .transition_opportunities import synthesize_transition_opportunities
from .transition_refinement_models import TransitionRefinementReport


def compile_ctl(
    edit_plan: EditPlan,
    vir: VirProject,
    fps: int = 24,
    width: int = 960,
    transition_refinement: TransitionRefinementReport | None = None,
) -> CtlProgram:
    if transition_refinement is not None and transition_refinement.project_id != edit_plan.project_id:
        raise ValueError("Transition refinement projectId does not match edit plan")

    shots = {shot.id: shot for shot in vir.shots}
    clips = [
        CtlClip(
            id=segment.id,
            asset_id=segment.asset_id,
            shot_id=segment.shot_id,
            source_in_seconds=segment.source_in_seconds,
            source_out_seconds=segment.source_out_seconds,
            timeline_in_seconds=segment.timeline_in_seconds,
            timeline_out_seconds=segment.timeline_out_seconds,
        )
        for segment in edit_plan.segments
    ]

    time_warps = select_timewarp_intents(edit_plan, vir, max_intents=2)
    warped_segment_ids = {intent.segment_id for intent in time_warps}
    opportunity_report = synthesize_transition_opportunities(edit_plan, vir)
    opportunities = {boundary.boundary_index: boundary for boundary in opportunity_report.boundaries}
    refinements = {
        boundary.boundary_index: boundary
        for boundary in transition_refinement.boundaries
    } if transition_refinement is not None else {}

    transitions: list[CtlTransition] = []
    for boundary_index, (left, right) in enumerate(zip(edit_plan.segments, edit_plan.segments[1:]), start=1):
        left_shot = shots.get(left.shot_id)
        right_shot = shots.get(right.shot_id)
        if left_shot is None or right_shot is None:
            transitions.append(CtlTransition(
                boundary_index=boundary_index,
                mechanism="hard_cut",
                reason="Shot analysis is unavailable at this boundary; preserve a deterministic hard cut.",
            ))
            continue

        signature = build_cut_signature(left, right, left_shot, right_shot)
        evidence: dict[str, float | str | bool] = {
            "directionCompatibility": signature.direction_compatibility,
            "zoomCompatibility": signature.zoom_compatibility,
            "phaseCompatibility": signature.phase_compatibility,
            "globalMotionConfidence": signature.global_motion_confidence,
            "leftDirection": left_shot.global_motion.dominant_screen_direction,
            "rightDirection": right_shot.global_motion.dominant_screen_direction,
        }

        opportunity = opportunities.get(boundary_index)
        refinement = refinements.get(boundary_index)
        if refinement is not None:
            if opportunity is None:
                raise ValueError(f"Transition refinement references missing boundary {boundary_index}")
            if refinement.base_mechanism != opportunity.recommended_mechanism:
                raise ValueError(
                    f"Transition refinement for boundary {boundary_index} is stale: "
                    f"base={refinement.base_mechanism} current={opportunity.recommended_mechanism}"
                )
            evidence["advancedRefinementStatus"] = refinement.status
            evidence["advancedBaseMechanism"] = refinement.base_mechanism
            evidence["advancedRefinedMechanism"] = refinement.refined_mechanism
            if refinement.flow_direction_compatibility is not None:
                evidence["advancedFlowDirectionCompatibility"] = refinement.flow_direction_compatibility
            if refinement.left_directional_coherence is not None:
                evidence["advancedLeftDirectionalCoherence"] = refinement.left_directional_coherence
            if refinement.right_directional_coherence is not None:
                evidence["advancedRightDirectionalCoherence"] = refinement.right_directional_coherence

            if refinement.status == "demoted":
                if refinement.refined_mechanism == "hard_cut":
                    transitions.append(CtlTransition(
                        boundary_index=boundary_index,
                        mechanism="hard_cut",
                        duration_seconds=0.0,
                        relation_score=signature.relation_score,
                        evidence=evidence,
                        reason=(
                            "Selective dense flow contradicted the coarse directional match; preserve a deliberate hard cut "
                            "instead of compiling the proposed bridge."
                        ),
                    ))
                    continue
                if refinement.refined_mechanism == "action_cut":
                    transitions.append(CtlTransition(
                        boundary_index=boundary_index,
                        mechanism="motion_peak_cut",
                        duration_seconds=0.0,
                        relation_score=signature.relation_score,
                        evidence=evidence,
                        reason=(
                            "Selective dense flow contradicted the directional bridge, while existing motion-phase evidence "
                            "still supports a zero-duration cut-on-action boundary."
                        ),
                    ))
                    continue

        if opportunity is not None:
            evidence["outgoingHandleSeconds"] = opportunity.outgoing_handle_seconds
            evidence["incomingHandleSeconds"] = opportunity.incoming_handle_seconds
            recommended = next(
                (
                    candidate
                    for candidate in opportunity.candidates
                    if candidate.mechanism == opportunity.recommended_mechanism
                ),
                None,
            )
            adjacent_timewarp = left.id in warped_segment_ids or right.id in warped_segment_ids
            evidence["adjacentTimewarp"] = adjacent_timewarp

            if (
                recommended is not None
                and recommended.mechanism == "directional_bridge"
                and recommended.feasible
                and not adjacent_timewarp
            ):
                transitions.append(CtlTransition(
                    boundary_index=boundary_index,
                    mechanism="directional_bridge",
                    duration_seconds=recommended.duration_seconds,
                    relation_score=signature.relation_score,
                    evidence=evidence,
                    parameters=recommended.parameters,
                    reason=(
                        "A physically motivated directional bridge has verified source handles on both sides; "
                        "compile it as a deterministic duration-preserving overlap primitive."
                    ),
                ))
                continue

            if recommended is not None and recommended.mechanism in {"directional_bridge", "zoom_bridge"}:
                evidence["bridgeDeferred"] = True
                if adjacent_timewarp:
                    evidence["bridgeDeferredReason"] = "adjacent_timewarp"
                elif recommended.mechanism == "zoom_bridge":
                    evidence["bridgeDeferredReason"] = "primitive_not_compiled_yet"
                else:
                    evidence["bridgeDeferredReason"] = "feasibility_guard"

        if signature.direction_compatibility >= 0.9 and signature.global_motion_confidence >= 0.35 and signature.relation_score >= 0.55:
            mechanism = "motion_match_cut"
            reason = "Adjacent shots share a confident global screen-motion direction; the zero-duration cut itself carries the transition."
        elif signature.phase_compatibility >= 0.6:
            mechanism = "motion_peak_cut"
            reason = "The boundary is aligned to a measured action phase even without a confident global direction match."
        else:
            mechanism = "hard_cut"
            reason = "Physical continuity evidence is weak; preserve a deliberate hard cut instead of inventing an effect."

        transitions.append(CtlTransition(
            boundary_index=boundary_index,
            mechanism=mechanism,
            duration_seconds=0.0,
            relation_score=signature.relation_score,
            evidence=evidence,
            reason=reason,
        ))

    return CtlProgram(
        project_id=edit_plan.project_id,
        duration_seconds=edit_plan.actual_duration_seconds,
        clips=clips,
        transitions=transitions,
        time_warps=time_warps,
        render_fps=fps,
        render_width=width,
    )
