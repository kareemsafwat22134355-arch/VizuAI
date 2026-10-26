from __future__ import annotations

from pathlib import Path

from .advanced_analysis import build_advanced_analysis_plan
from .advanced_executor import execute_advanced_analysis
from .analysis import analyze_project
from .audio import analyze_audio
from .audio_mix_audit import audit_audio_mix
from .critic import critique_edit
from .ctl import compile_ctl
from .director import default_director_plan
from .ingest import ingest_project
from .manifest_io import write_model
from .microscope_models import StyleProfile
from .otio_export import export_otio
from .planner import build_edit_plan
from .production_models import ProductionReport
from .proxy import create_project_proxies
from .render import render_draft
from .revision import revise_edit_plan
from .sound_director import build_sound_directed_audio_plan, direct_sound
from .transition_opportunities import synthesize_transition_opportunities
from .transition_refinement import refine_transition_opportunities


def produce_project(
    source_root: Path,
    project_name: str,
    work_dir: Path,
    music: Path | None = None,
    duration: float = 15.0,
    width: int = 960,
    fps: int = 24,
    max_revision_iterations: int = 2,
    render: bool = True,
    style_profile: StyleProfile | None = None,
    max_advanced_boundaries: int = 4,
    run_advanced_pass: bool = True,
    advanced_sample_fps: float = 12.0,
    advanced_analysis_width: int = 320,
    run_sound_pass: bool = True,
    max_jl_cuts: int = 2,
    audio_safety_threshold_dbfs: float = -0.5,
) -> ProductionReport:
    if max_revision_iterations < 0 or max_revision_iterations > 4:
        raise ValueError("max_revision_iterations must be between 0 and 4")
    if max_advanced_boundaries < 1:
        raise ValueError("max_advanced_boundaries must be >= 1")
    if advanced_sample_fps <= 0:
        raise ValueError("advanced_sample_fps must be > 0")
    if advanced_analysis_width < 64:
        raise ValueError("advanced_analysis_width must be >= 64")
    if max_jl_cuts < 0 or max_jl_cuts > 8:
        raise ValueError("max_jl_cuts must be between 0 and 8")

    work_dir.mkdir(parents=True, exist_ok=True)
    proxy_dir = work_dir / "proxies"
    analysis_cache_dir = work_dir / "analysis-cache"

    project = ingest_project(source_root, project_name)
    create_project_proxies(project, source_root, proxy_dir, width=width, fps=fps)
    write_model(work_dir / "project.monter.json", project)

    vir = analyze_project(project, proxy_dir, cache_dir=analysis_cache_dir)
    write_model(work_dir / "vir.monter.json", vir)
    if not vir.shots:
        raise ValueError("No analyzable shots were produced; inspect VIR warnings before continuing")

    director = default_director_plan(duration)
    write_model(work_dir / "director-plan.json", director)

    audio = analyze_audio(music) if music else None
    if audio:
        write_model(work_dir / "audio-analysis.json", audio)

    edit = build_edit_plan(vir, director, audio, style_profile=style_profile)
    ctl = compile_ctl(edit, vir, fps=fps, width=width)
    critic = critique_edit(edit, ctl, vir)
    write_model(work_dir / "critic-00.json", critic)

    revision_iterations = 0
    for iteration in range(1, max_revision_iterations + 1):
        if critic.status == "pass":
            break
        revised, revision_report = revise_edit_plan(edit, vir, critic)
        write_model(work_dir / f"revision-{iteration:02d}.json", revision_report)
        if not revision_report.changed:
            break
        edit = revised
        ctl = compile_ctl(edit, vir, fps=fps, width=width)
        critic = critique_edit(edit, ctl, vir)
        write_model(work_dir / f"critic-{iteration:02d}.json", critic)
        revision_iterations = iteration

    # Expensive boundary evidence is intentionally scheduled only after the rough edit
    # and bounded revision loop are stable, so selected source windows cannot become stale.
    transitions = synthesize_transition_opportunities(edit, vir)
    advanced_analysis = build_advanced_analysis_plan(
        ctl,
        transitions,
        max_boundaries=max_advanced_boundaries,
    )

    write_model(work_dir / "edit-plan.json", edit)
    write_model(work_dir / "transition-opportunities.json", transitions)
    write_model(work_dir / "advanced-analysis-plan.json", advanced_analysis)

    advanced_boundaries_executed = 0
    transition_refinements_applied = 0
    if run_advanced_pass:
        advanced_results = execute_advanced_analysis(
            project,
            advanced_analysis,
            proxy_dir,
            sample_fps=advanced_sample_fps,
            analysis_width=min(advanced_analysis_width, width),
        )
        write_model(work_dir / "advanced-analysis-results.json", advanced_results)
        advanced_boundaries_executed = len(advanced_results.boundaries)

        transition_refinement = refine_transition_opportunities(transitions, advanced_results)
        write_model(work_dir / "transition-refinement.json", transition_refinement)
        transition_refinements_applied = sum(
            boundary.status in {"confirmed", "demoted"}
            for boundary in transition_refinement.boundaries
        )
        ctl = compile_ctl(
            edit,
            vir,
            fps=fps,
            width=width,
            transition_refinement=transition_refinement,
        )
        # The final critic must inspect the same CTL that will actually be rendered.
        critic = critique_edit(edit, ctl, vir)

    write_model(work_dir / "ctl.json", ctl)
    write_model(work_dir / "critic-report.json", critic)
    export_otio(project, edit, work_dir / "edit.otio")

    audio_plan = None
    sound_non_sync_selected = 0
    if run_sound_pass:
        sound_report = direct_sound(
            project,
            ctl,
            vir,
            proxy_dir,
            max_jl_cuts=max_jl_cuts,
        )
        write_model(work_dir / "sound-director.json", sound_report)
        sound_non_sync_selected = len(sound_report.selected_intents)
        audio_plan = build_sound_directed_audio_plan(project, ctl, sound_report)
        write_model(work_dir / "audio-edit-plan.json", audio_plan)

    audio_mix_audited = False
    audio_mix_safe: bool | None = None
    mix_warning: str | None = None
    if render:
        output = work_dir / "rough-cut.mp4"
        render_draft(
            ctl,
            project,
            proxy_dir,
            output,
            music,
            audio_plan=audio_plan,
        )
        has_rendered_audio = music is not None or (audio_plan is not None and bool(audio_plan.events))
        if has_rendered_audio:
            audit = audit_audio_mix(output, safety_threshold_dbfs=audio_safety_threshold_dbfs)
            write_model(work_dir / "audio-mix-audit.json", audit)
            audio_mix_audited = True
            audio_mix_safe = audit.clipping_safe
            if not audit.clipping_safe:
                mix_warning = (
                    f"Rendered audio mix failed headroom gate: max={audit.max_volume_dbfs:.1f} dBFS "
                    f"> threshold={audit.safety_threshold_dbfs:.1f} dBFS."
                )

    artifacts = [
        "project.monter.json",
        "vir.monter.json",
        "director-plan.json",
        "edit-plan.json",
        "ctl.json",
        "critic-report.json",
        "transition-opportunities.json",
        "advanced-analysis-plan.json",
        "edit.otio",
    ]
    if audio:
        artifacts.append("audio-analysis.json")
    if run_advanced_pass:
        artifacts.extend(["advanced-analysis-results.json", "transition-refinement.json"])
    if run_sound_pass:
        artifacts.extend(["sound-director.json", "audio-edit-plan.json"])
    if render:
        artifacts.append("rough-cut.mp4")
    if audio_mix_audited:
        artifacts.append("audio-mix-audit.json")

    warnings = list(vir.warnings)
    warnings.extend(finding.message for finding in critic.findings if finding.severity == "error")
    if mix_warning:
        warnings.append(mix_warning)

    production_passed = critic.status == "pass" and audio_mix_safe is not False
    report = ProductionReport(
        project_id=project.project_id,
        status="pass" if production_passed else "needs_review",
        revision_iterations=revision_iterations,
        assets_ingested=len(project.assets),
        shots_analyzed=len(vir.shots),
        edit_segments=len(edit.segments),
        target_duration_seconds=edit.target_duration_seconds,
        actual_duration_seconds=edit.actual_duration_seconds,
        advanced_pass_executed=run_advanced_pass,
        advanced_boundaries_executed=advanced_boundaries_executed,
        transition_refinements_applied=transition_refinements_applied,
        sound_pass_executed=run_sound_pass,
        sound_non_sync_selected=sound_non_sync_selected,
        audio_mix_audited=audio_mix_audited,
        audio_mix_safe=audio_mix_safe,
        artifacts=artifacts,
        warnings=warnings,
    )
    write_model(work_dir / "production-report.json", report)
    return report
