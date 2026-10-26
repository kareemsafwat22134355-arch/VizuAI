from __future__ import annotations

import argparse
from pathlib import Path

from .analysis import analyze_project
from .audio import analyze_audio
from .ctl import compile_ctl
from .director import default_director_plan
from .ingest import ingest_project
from .manifest_io import load_ctl, load_edit_plan, load_project, load_vir, write_model
from .otio_export import export_otio
from .planner import build_edit_plan
from .proxy import create_project_proxies
from .render import render_draft


def add_shared_media_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--width", type=int, default=960, help="analysis/render proxy max width")
    parser.add_argument("--fps", type=int, default=24, help="analysis/render frame rate")


def add_plan_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--duration", type=float, default=15.0, help="target edit duration in seconds")
    parser.add_argument("--music", default=None, help="optional music track for beat/onset analysis")


def write_planning_outputs(vir_path: Path, out_dir: Path, duration: float, music: str | None):
    vir = load_vir(vir_path)
    director = default_director_plan(duration)
    audio = analyze_audio(Path(music)) if music else None
    edit_plan = build_edit_plan(vir, director, audio)

    out_dir.mkdir(parents=True, exist_ok=True)
    write_model(out_dir / "director-plan.json", director)
    write_model(out_dir / "edit-plan.json", edit_plan)
    if audio:
        write_model(out_dir / "audio-analysis.json", audio)

    print(
        f"Edit plan ready: {len(edit_plan.segments)} segments, "
        f"{edit_plan.actual_duration_seconds:.2f}s actual / {duration:.2f}s target"
    )
    return edit_plan


def main() -> None:
    parser = argparse.ArgumentParser(prog="monter", description="MONTER local media bridge")
    sub = parser.add_subparsers(dest="command", required=True)

    ingest = sub.add_parser("ingest", help="index a RAW footage folder without uploading it")
    ingest.add_argument("folder")
    ingest.add_argument("--name", default="MONTER Project")
    ingest.add_argument("--out", default="project.monter.json")

    proxy = sub.add_parser("proxy", help="generate lightweight analysis proxies")
    proxy.add_argument("source_root")
    proxy.add_argument("--manifest", default="project.monter.json")
    proxy.add_argument("--out-dir", default=".monter/proxies")
    add_shared_media_args(proxy)

    analyze = sub.add_parser("analyze", help="build VIR shot and motion intelligence from proxies")
    analyze.add_argument("--manifest", default="project.monter.json")
    analyze.add_argument("--proxy-dir", default=".monter/proxies")
    analyze.add_argument("--out", default="vir.monter.json")

    plan = sub.add_parser("plan", help="build a director plan and rough edit from VIR")
    plan.add_argument("--vir", default=".monter/vir.monter.json")
    plan.add_argument("--out-dir", default=".monter")
    add_plan_args(plan)

    compile_parser = sub.add_parser("compile", help="compile an edit plan into validated CTL")
    compile_parser.add_argument("--edit-plan", default=".monter/edit-plan.json")
    compile_parser.add_argument("--vir", default=".monter/vir.monter.json")
    compile_parser.add_argument("--out", default=".monter/ctl.json")
    add_shared_media_args(compile_parser)

    render_parser = sub.add_parser("render", help="render a deterministic proxy draft from CTL")
    render_parser.add_argument("--manifest", default=".monter/project.monter.json")
    render_parser.add_argument("--ctl", default=".monter/ctl.json")
    render_parser.add_argument("--proxy-dir", default=".monter/proxies")
    render_parser.add_argument("--music", default=None)
    render_parser.add_argument("--out", default=".monter/rough-cut.mp4")

    otio_parser = sub.add_parser("export-otio", help="export the edit plan as OpenTimelineIO")
    otio_parser.add_argument("--manifest", default=".monter/project.monter.json")
    otio_parser.add_argument("--edit-plan", default=".monter/edit-plan.json")
    otio_parser.add_argument("--out", default=".monter/edit.otio")

    prepare = sub.add_parser("prepare", help="ingest RAW, create proxies, analyze, plan, and compile CTL")
    prepare.add_argument("folder")
    prepare.add_argument("--name", default="MONTER Project")
    prepare.add_argument("--work-dir", default=".monter")
    add_shared_media_args(prepare)
    add_plan_args(prepare)

    args = parser.parse_args()

    if args.command == "ingest":
        project = ingest_project(Path(args.folder), args.name)
        write_model(Path(args.out), project)
        print(f"Indexed {len(project.assets)} assets -> {args.out}")
        return

    if args.command == "proxy":
        project = load_project(Path(args.manifest))
        created, total_bytes = create_project_proxies(
            project,
            source_root=Path(args.source_root),
            out_dir=Path(args.out_dir),
            width=args.width,
            fps=args.fps,
        )
        write_model(Path(args.manifest), project)
        print(f"Proxies ready: {created} created/refreshed, {total_bytes} bytes total")
        return

    if args.command == "analyze":
        project = load_project(Path(args.manifest))
        vir = analyze_project(project, Path(args.proxy_dir))
        write_model(Path(args.out), vir)
        print(f"VIR ready: {len(vir.shots)} shots, {len(vir.warnings)} warnings -> {args.out}")
        return

    if args.command == "plan":
        write_planning_outputs(Path(args.vir), Path(args.out_dir), args.duration, args.music)
        return

    if args.command == "compile":
        edit_plan = load_edit_plan(Path(args.edit_plan))
        vir = load_vir(Path(args.vir))
        ctl = compile_ctl(edit_plan, vir, fps=args.fps, width=args.width)
        write_model(Path(args.out), ctl)
        print(f"CTL ready: {len(ctl.clips)} clips, {len(ctl.transitions)} boundaries -> {args.out}")
        return

    if args.command == "render":
        project = load_project(Path(args.manifest))
        ctl = load_ctl(Path(args.ctl))
        render_draft(ctl, project, Path(args.proxy_dir), Path(args.out), Path(args.music) if args.music else None)
        print(f"Draft rendered -> {args.out}")
        return

    if args.command == "export-otio":
        project = load_project(Path(args.manifest))
        edit_plan = load_edit_plan(Path(args.edit_plan))
        export_otio(project, edit_plan, Path(args.out))
        print(f"OTIO exported -> {args.out}")
        return

    if args.command == "prepare":
        source_root = Path(args.folder)
        work_dir = Path(args.work_dir)
        work_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = work_dir / "project.monter.json"
        proxy_dir = work_dir / "proxies"
        vir_path = work_dir / "vir.monter.json"

        project = ingest_project(source_root, args.name)
        create_project_proxies(project, source_root, proxy_dir, width=args.width, fps=args.fps)
        write_model(manifest_path, project)
        vir = analyze_project(project, proxy_dir)
        write_model(vir_path, vir)
        print(
            f"Prepared media: {project.project_name}: {len(project.assets)} assets, "
            f"{len(vir.shots)} shots, {len(vir.warnings)} warnings"
        )
        edit_plan = write_planning_outputs(vir_path, work_dir, args.duration, args.music)
        ctl = compile_ctl(edit_plan, vir, fps=args.fps, width=args.width)
        write_model(work_dir / "ctl.json", ctl)
        print(f"CTL ready: {len(ctl.clips)} clips, {len(ctl.transitions)} boundaries")


if __name__ == "__main__":
    main()
