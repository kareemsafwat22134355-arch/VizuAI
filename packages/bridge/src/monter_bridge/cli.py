from __future__ import annotations

import argparse
from pathlib import Path

from .analysis import analyze_project
from .ingest import ingest_project
from .manifest_io import load_project, write_model
from .proxy import create_project_proxies


def add_shared_media_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--width", type=int, default=960, help="analysis proxy max width")
    parser.add_argument("--fps", type=int, default=24, help="analysis proxy frame rate")


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

    prepare = sub.add_parser("prepare", help="ingest RAW, create proxies, then build the first VIR")
    prepare.add_argument("folder")
    prepare.add_argument("--name", default="MONTER Project")
    prepare.add_argument("--work-dir", default=".monter")
    add_shared_media_args(prepare)

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
            f"Prepared {project.project_name}: {len(project.assets)} assets, "
            f"{len(vir.shots)} shots, {len(vir.warnings)} warnings -> {work_dir}"
        )


if __name__ == "__main__":
    main()
