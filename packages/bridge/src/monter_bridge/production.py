from __future__ import annotations

from pathlib import Path

from .analysis import analyze_project
from .audio import analyze_audio
from .critic import critique_edit
from .ctl import compile_ctl
from .director import default_director_plan
from .ingest import ingest_project
from .manifest_io import write_model
from .otio_export import export_otio
from .planner import build_edit_plan
from .production_models import ProductionReport
from .proxy import create_project_proxies
from .render import render_draft
from .revision import revise_edit_plan


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
) -> ProductionReport:
    if max_revision_iterations < 0 or max_revision_iterations > 4:
        raise ValueError("max_revision_iterations must be between 0 and 4")

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

    edit = build_edit_plan(vir, director, audio)
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

    write_model(work_dir / "edit-plan.json", edit)
    write_model(work_dir / "ctl.json", ctl)
    write_model(work_dir / "critic-report.json", critic)
    export_otio(project, edit, work_dir / "edit.otio")

    if render:
        render_draft(
            ctl,
            project,
            proxy_dir,
            work_dir / "rough-cut.mp4",
            music,
        )

    artifacts = [
        "project.monter.json",
        "vir.monter.json",
        "director-plan.json",
        "edit-plan.json",
        "ctl.json",
        "critic-report.json",
        "edit.otio",
    ]
    if audio:
        artifacts.append("audio-analysis.json")
    if render:
        artifacts.append("rough-cut.mp4")

    report = ProductionReport(
        project_id=project.project_id,
        status="pass" if critic.status == "pass" else "needs_review",
        revision_iterations=revision_iterations,
        assets_ingested=len(project.assets),
        shots_analyzed=len(vir.shots),
        edit_segments=len(edit.segments),
        target_duration_seconds=edit.target_duration_seconds,
        actual_duration_seconds=edit.actual_duration_seconds,
        artifacts=artifacts,
        warnings=vir.warnings + [finding.message for finding in critic.findings if finding.severity == "error"],
    )
    write_model(work_dir / "production-report.json", report)
    return report
