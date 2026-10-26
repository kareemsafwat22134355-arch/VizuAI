from __future__ import annotations

import argparse
from pathlib import Path

from .manifest_io import load_ctl, load_project, load_vir, write_model
from .sound_director import build_sound_directed_audio_plan, direct_sound


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze local source audio and propose a small number of motivated J/L cuts")
    parser.add_argument("--manifest", default=".monter/project.monter.json")
    parser.add_argument("--ctl", default=".monter/ctl.json")
    parser.add_argument("--vir", default=".monter/vir.monter.json")
    parser.add_argument("--proxy-dir", default=".monter/proxies")
    parser.add_argument("--max-jl-cuts", type=int, default=2)
    parser.add_argument("--source-gain-db", type=float, default=-3.0)
    parser.add_argument("--music-gain-db", type=float, default=-8.0)
    parser.add_argument("--report-out", default=".monter/sound-director.json")
    parser.add_argument("--audio-plan-out", default=".monter/audio-edit-plan.json")
    args = parser.parse_args()

    project = load_project(Path(args.manifest))
    ctl = load_ctl(Path(args.ctl))
    vir = load_vir(Path(args.vir))
    report = direct_sound(project, ctl, vir, Path(args.proxy_dir), max_jl_cuts=args.max_jl_cuts)
    audio_plan = build_sound_directed_audio_plan(
        project,
        ctl,
        report,
        source_gain_db=args.source_gain_db,
        music_gain_db=args.music_gain_db,
    )
    write_model(Path(args.report_out), report)
    write_model(Path(args.audio_plan_out), audio_plan)

    j_count = sum(item.recommendation == "j_cut" for item in report.selected_intents)
    l_count = sum(item.recommendation == "l_cut" for item in report.selected_intents)
    sync_count = sum(item.recommendation == "sync" for item in report.decisions)
    print(
        f"Sound Director: {len(report.decisions)} boundaries, selected J={j_count} L={l_count}, "
        f"sync={sync_count} -> {args.report_out} + {args.audio_plan_out}"
    )


if __name__ == "__main__":
    main()
