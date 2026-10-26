from __future__ import annotations

from .analysis_models import VirProject
from .ctl_models import CtlClip, CtlProgram, CtlTransition
from .cut_signature import build_cut_signature
from .models import MonterProject
from .planning_models import EditPlan
from .sound import select_audio_boundaries
from .timewarp import select_timewarp_intents


def compile_ctl(
    edit_plan: EditPlan,
    vir: VirProject,
    fps: int = 24,
    width: int = 960,
    project: MonterProject | None = None,
) -> CtlProgram:
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

        if signature.direction_compatibility >= 0.9 and signature.global_motion_confidence >= 0.35 and signature.relation_score >= 0.55:
            mechanism = "motion_match_cut"
            reason = "Adjacent shots share a confident global screen-motion direction; the cut itself carries the transition."
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

    time_warps = select_timewarp_intents(edit_plan, vir, max_intents=2)
    audio_boundaries = select_audio_boundaries(edit_plan, project, time_warps, max_intents=1) if project else []

    return CtlProgram(
        project_id=edit_plan.project_id,
        duration_seconds=edit_plan.actual_duration_seconds,
        clips=clips,
        transitions=transitions,
        time_warps=time_warps,
        audio_boundaries=audio_boundaries,
        render_fps=fps,
        render_width=width,
    )
