from __future__ import annotations

import argparse
from pathlib import Path

from .manifest_io import load_audio_edit_plan, load_ctl, load_project
from .render import render_draft


def main() -> None:
    parser = argparse.ArgumentParser(description="Render CTL with an explicit source-audio/J-L edit plan")
    parser.add_argument("--manifest", default=".monter/project.monter.json")
    parser.add_argument("--ctl", default=".monter/ctl.json")
    parser.add_argument("--audio-plan", default=".monter/audio-edit-plan.json")
    parser.add_argument("--proxy-dir", default=".monter/proxies")
    parser.add_argument("--music", default=None)
    parser.add_argument("--out", default=".monter/rough-cut.audio.mp4")
    args = parser.parse_args()

    project = load_project(Path(args.manifest))
    ctl = load_ctl(Path(args.ctl))
    audio_plan = load_audio_edit_plan(Path(args.audio_plan))
    render_draft(
        ctl,
        project,
        Path(args.proxy_dir),
        Path(args.out),
        Path(args.music) if args.music else None,
        audio_plan=audio_plan,
    )
    print(
        f"Audio-aware draft rendered: {len(audio_plan.events)} source event(s), "
        f"{len(audio_plan.boundaries)} J/L boundary intent(s) -> {args.out}"
    )


if __name__ == "__main__":
    main()
