from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil

from .advanced_analysis import build_advanced_analysis_plan
from .advanced_executor import execute_advanced_analysis
from .analysis_models import VirProject
from .audio_edit_models import AudioEditPlan
from .audio_mix_audit import audit_audio_mix
from .audio_mix_models import AudioMixAudit
from .critic import critique_edit
from .critic_models import CriticReport
from .ctl import compile_ctl
from .ctl_models import CtlProgram
from .final_critic import build_final_critic
from .final_critic_models import FinalCriticReport
from .manifest_io import write_model
from .models import MonterProject
from .otio_export import export_otio
from .planning_models import DirectorPlan, EditPlan
from .post_render_revision_models import PostRenderRevisionReport
from .render import render_draft
from .render_analysis import analyze_render
from .render_analysis_models import RenderAnalysisReport
from .revision import revise_edit_plan
from .sound_director import build_sound_directed_audio_plan, direct_sound
from .transition_opportunities import synthesize_transition_opportunities
from .transition_refinement import refine_transition_opportunities


AUTO_REVISION_CODES = {
    "energy_mismatch",
    "low_confidence_selection",
    "immediate_repetition",
    "motion_match_timing_weak",
}

PROMOTABLE_ARTIFACTS = (
    "edit-plan.json",
    "ctl.json",
    "critic-report.json",
    "transition-opportunities.json",
    "advanced-analysis-plan.json",
    "advanced-analysis-results.json",
    "transition-refinement.json",
    "sound-director.json",
    "audio-edit-plan.json",
    "edit.otio",
    "rough-cut.mp4",
    "audio-mix-audit.json",
    "render-analysis.json",
    "final-critic-report.json",
)


@dataclass
class AcceptedCandidateState:
    edit: EditPlan
    ctl: CtlProgram
    critic: CriticReport
    final_critic: FinalCriticReport
    audio_audit: AudioMixAudit | None
    render_analysis: RenderAnalysisReport
    audio_plan: AudioEditPlan | None
    advanced_boundaries_executed: int
    transition_refinements_applied: int
    sound_non_sync_selected: int


def should_attempt_post_render_revision(final_critic: FinalCriticReport) -> bool:
    return (
        final_critic.status == "needs_revision"
        and final_critic.automatic_revision_candidates > 0
        and not any(
            finding.severity == "error"
            and finding.domain in {"render_integrity", "audio_integrity"}
            for finding in final_critic.findings
        )
    )


def filter_automatic_editorial_critic(
    editorial: CriticReport,
    final_critic: FinalCriticReport,
) -> CriticReport:
    if editorial.project_id != final_critic.project_id:
        raise ValueError("Final critic projectId does not match editorial critic")

    candidate_keys = {
        (finding.code, finding.segment_id, finding.boundary_index)
        for finding in final_critic.findings
        if finding.domain == "editorial"
        and finding.reviseability == "automatic_candidate"
        and finding.code in AUTO_REVISION_CODES
    }
    findings = [
        finding
        for finding in editorial.findings
        if (finding.code, finding.segment_id, finding.boundary_index) in candidate_keys
    ]
    return CriticReport(
        project_id=editorial.project_id,
        status="needs_revision" if findings else "pass",
        metrics=editorial.metrics,
        findings=findings,
        notes=[
            "Filtered post-render critic contains only editorial findings already supported by deterministic revision actions."
        ],
    )


def _reset_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def _snapshot_baseline(work_dir: Path, baseline_dir: Path) -> list[str]:
    _reset_dir(baseline_dir)
    copied: list[str] = []
    for name in PROMOTABLE_ARTIFACTS:
        source = work_dir / name
        if not source.is_file():
            continue
        shutil.copy2(source, baseline_dir / name)
        copied.append(name)
    return copied


def _promote_candidate(candidate_dir: Path, work_dir: Path) -> list[str]:
    promoted: list[str] = []
    for name in PROMOTABLE_ARTIFACTS:
        source = candidate_dir / name
        if not source.is_file():
            continue
        shutil.copy2(source, work_dir / name)
        promoted.append(name)
    return promoted


def attempt_post_render_revision(
    *,
    project: MonterProject,
    vir: VirProject,
    director: DirectorPlan,
    baseline_edit: EditPlan,
    baseline_editorial_critic: CriticReport,
    baseline_final_critic: FinalCriticReport,
    work_dir: Path,
    proxy_dir: Path,
    music: Path | None,
    width: int,
    fps: int,
    run_advanced_pass: bool,
    max_advanced_boundaries: int,
    advanced_sample_fps: float,
    advanced_analysis_width: int,
    run_sound_pass: bool,
    max_jl_cuts: int,
    audio_safety_threshold_dbfs: float,
    render_analysis_sample_fps: float,
    render_analysis_width: int,
) -> tuple[PostRenderRevisionReport, AcceptedCandidateState | None]:
    eligible = should_attempt_post_render_revision(baseline_final_critic)
    if not eligible:
        return PostRenderRevisionReport(
            project_id=project.project_id,
            eligible=False,
            attempted=False,
            changed=False,
            accepted=False,
            reason=(
                "Final Critic did not expose a safe post-render automatic editorial candidate, "
                "or output-integrity evidence blocks automatic mutation."
            ),
            baseline_final_status=baseline_final_critic.status,
            baseline_automatic_candidates=baseline_final_critic.automatic_revision_candidates,
            notes=["At most one post-render candidate attempt is permitted."],
        ), None

    filtered = filter_automatic_editorial_critic(baseline_editorial_critic, baseline_final_critic)
    revised_edit, revision_report = revise_edit_plan(baseline_edit, vir, filtered)
    changed_segments = [
        action.segment_id
        for action in revision_report.actions
        if action.kind == "replace_segment" and action.segment_id is not None
    ]
    changed_boundaries = [
        action.boundary_index
        for action in revision_report.actions
        if action.kind == "realign_boundary" and action.boundary_index is not None
    ]
    if not revision_report.changed:
        return PostRenderRevisionReport(
            project_id=project.project_id,
            eligible=True,
            attempted=True,
            changed=False,
            accepted=False,
            reason="Revision engine found no deterministic action that could satisfy the eligible final-critic finding(s).",
            baseline_final_status=baseline_final_critic.status,
            baseline_automatic_candidates=baseline_final_critic.automatic_revision_candidates,
            changed_segments=changed_segments,
            changed_boundaries=changed_boundaries,
            notes=["No candidate render was created because the edit did not change."],
        ), None

    candidate_dir = work_dir / "post-render-candidate-01"
    _reset_dir(candidate_dir)
    write_model(candidate_dir / "revision-report.json", revision_report)
    write_model(candidate_dir / "edit-plan.json", revised_edit)

    base_ctl = compile_ctl(revised_edit, vir, fps=fps, width=width)
    transitions = synthesize_transition_opportunities(revised_edit, vir)
    advanced_plan = build_advanced_analysis_plan(
        base_ctl,
        transitions,
        max_boundaries=max_advanced_boundaries,
    )
    write_model(candidate_dir / "transition-opportunities.json", transitions)
    write_model(candidate_dir / "advanced-analysis-plan.json", advanced_plan)

    ctl = base_ctl
    advanced_boundaries_executed = 0
    transition_refinements_applied = 0
    if run_advanced_pass:
        advanced_results = execute_advanced_analysis(
            project,
            advanced_plan,
            proxy_dir,
            sample_fps=advanced_sample_fps,
            analysis_width=min(advanced_analysis_width, width),
        )
        write_model(candidate_dir / "advanced-analysis-results.json", advanced_results)
        advanced_boundaries_executed = len(advanced_results.boundaries)
        refinement = refine_transition_opportunities(transitions, advanced_results)
        write_model(candidate_dir / "transition-refinement.json", refinement)
        transition_refinements_applied = sum(
            boundary.status in {"confirmed", "demoted"}
            for boundary in refinement.boundaries
        )
        ctl = compile_ctl(
            revised_edit,
            vir,
            fps=fps,
            width=width,
            transition_refinement=refinement,
        )

    editorial_critic = critique_edit(revised_edit, ctl, vir)
    write_model(candidate_dir / "ctl.json", ctl)
    write_model(candidate_dir / "critic-report.json", editorial_critic)
    export_otio(project, revised_edit, candidate_dir / "edit.otio")

    audio_plan: AudioEditPlan | None = None
    sound_non_sync_selected = 0
    if run_sound_pass:
        sound_report = direct_sound(project, ctl, vir, proxy_dir, max_jl_cuts=max_jl_cuts)
        write_model(candidate_dir / "sound-director.json", sound_report)
        sound_non_sync_selected = len(sound_report.selected_intents)
        audio_plan = build_sound_directed_audio_plan(project, ctl, sound_report)
        write_model(candidate_dir / "audio-edit-plan.json", audio_plan)

    candidate_render = candidate_dir / "rough-cut.mp4"
    render_draft(
        ctl,
        project,
        proxy_dir,
        candidate_render,
        music,
        audio_plan=audio_plan,
    )

    has_rendered_audio = music is not None or (audio_plan is not None and bool(audio_plan.events))
    audio_audit: AudioMixAudit | None = None
    if has_rendered_audio:
        audio_audit = audit_audio_mix(candidate_render, safety_threshold_dbfs=audio_safety_threshold_dbfs)
        write_model(candidate_dir / "audio-mix-audit.json", audio_audit)

    render_report = analyze_render(
        candidate_render,
        project_id=project.project_id,
        expected_duration_seconds=revised_edit.actual_duration_seconds,
        director_plan=director,
        sample_fps=render_analysis_sample_fps,
        analysis_width=min(render_analysis_width, width),
    )
    write_model(candidate_dir / "render-analysis.json", render_report)

    candidate_final = build_final_critic(
        editorial_critic,
        render_analysis=render_report,
        audio_audit=audio_audit,
    )
    write_model(candidate_dir / "final-critic-report.json", candidate_final)

    accepted = candidate_final.status == "pass"
    baseline_dir: Path | None = None
    promoted: list[str] = []
    if accepted:
        baseline_dir = work_dir / "post-render-baseline"
        _snapshot_baseline(work_dir, baseline_dir)
        promoted = _promote_candidate(candidate_dir, work_dir)

    report = PostRenderRevisionReport(
        project_id=project.project_id,
        eligible=True,
        attempted=True,
        changed=True,
        accepted=accepted,
        reason=(
            "Candidate passed the full post-render Final Critic and was promoted after the canonical baseline was snapshotted."
            if accepted
            else "Candidate did not reach Final Critic pass; canonical baseline artifacts were left untouched."
        ),
        baseline_final_status=baseline_final_critic.status,
        candidate_final_status=candidate_final.status,
        baseline_automatic_candidates=baseline_final_critic.automatic_revision_candidates,
        candidate_automatic_candidates=candidate_final.automatic_revision_candidates,
        changed_segments=changed_segments,
        changed_boundaries=changed_boundaries,
        candidate_dir=candidate_dir.name,
        baseline_snapshot_dir=baseline_dir.name if baseline_dir is not None else None,
        promoted_artifacts=promoted,
        notes=[
            "Exactly one post-render edit candidate attempt is permitted.",
            "Render/audio integrity errors never authorize an edit mutation.",
            "Rejected candidates remain inspectable under post-render-candidate-01 while canonical artifacts stay unchanged.",
        ],
    )

    if not accepted:
        return report, None

    return report, AcceptedCandidateState(
        edit=revised_edit,
        ctl=ctl,
        critic=editorial_critic,
        final_critic=candidate_final,
        audio_audit=audio_audit,
        render_analysis=render_report,
        audio_plan=audio_plan,
        advanced_boundaries_executed=advanced_boundaries_executed,
        transition_refinements_applied=transition_refinements_applied,
        sound_non_sync_selected=sound_non_sync_selected,
    )
