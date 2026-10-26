from __future__ import annotations

from .analysis_models import ShotAnalysis, VirProject
from .ctl_models import CtlClip, CtlProgram, CtlTransition
from .planning_models import EditPlan


def _near_motion_peak(shot: ShotAnalysis, time_seconds: float, tolerance: float = 0.35) -> bool:
    return any(
        anchor.type == "motion_peak" and abs(anchor.time_seconds - time_seconds) <= tolerance
        for anchor in shot.edit_anchors
    )


def compile_ctl(edit_plan: EditPlan, vir: VirProject, fps: int = 24, width: int = 960) -> CtlProgram:
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
        motivated = bool(
            (left_shot and _near_motion_peak(left_shot, left.source_out_seconds))
            or (right_shot and _near_motion_peak(right_shot, right.source_in_seconds))
        )
        transitions.append(
            CtlTransition(
                boundary_index=boundary_index,
                mechanism="motion_peak_cut" if motivated else "hard_cut",
                duration_seconds=0.0,
                reason=(
                    "Cut boundary is adjacent to a measured motion apex."
                    if motivated
                    else "No stronger physical transition cue is available; preserve a deliberate hard cut."
                ),
            )
        )

    return CtlProgram(
        project_id=edit_plan.project_id,
        duration_seconds=edit_plan.actual_duration_seconds,
        clips=clips,
        transitions=transitions,
        render_fps=fps,
        render_width=width,
    )
