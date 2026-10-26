from __future__ import annotations

import argparse
from pathlib import Path

from .audio_edit import build_audio_edit_plan
from .audio_edit_models import AudioBoundaryIntent
from .manifest_io import load_ctl, load_project, write_model


def _parse_boundary_spec(value: str, kind: str) -> AudioBoundaryIntent:
    try:
        boundary_text, overlap_text = value.split(":", 1)
        boundary_index = int(boundary_text)
        overlap_seconds = float(overlap_text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"expected BOUNDARY:SECONDS, got {value!r}") from exc
    if boundary_index < 1 or overlap_seconds <= 0:
        raise argparse.ArgumentTypeError("boundary must be >= 1 and overlap must be > 0")
    return AudioBoundaryIntent(
        boundary_index=boundary_index,
        kind=kind,
        overlap_seconds=overlap_seconds,
        reason=f"Explicit {kind.replace('_', '-')} intent supplied by the editor for this boundary.",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a source-audio timeline with explicit J/L cuts")
    parser.add_argument("--manifest", default=".monter/project.monter.json")
    parser.add_argument("--ctl", default=".monter/ctl.json")
    parser.add_argument("--j-cut", action="append", default=[], metavar="BOUNDARY:SECONDS")
    parser.add_argument("--l-cut", action="append", default=[], metavar="BOUNDARY:SECONDS")
    parser.add_argument("--source-gain-db", type=float, default=-3.0)
    parser.add_argument("--music-gain-db", type=float, default=-8.0)
    parser.add_argument("--out", default=".monter/audio-edit-plan.json")
    args = parser.parse_args()

    intents = [
        *[_parse_boundary_spec(value, "j_cut") for value in args.j_cut],
        *[_parse_boundary_spec(value, "l_cut") for value in args.l_cut],
    ]
    boundary_ids = [intent.boundary_index for intent in intents]
    if len(boundary_ids) != len(set(boundary_ids)):
        raise SystemExit("Only one audio intent may target a visual boundary in v0.19")

    project = load_project(Path(args.manifest))
    ctl = load_ctl(Path(args.ctl))
    plan = build_audio_edit_plan(
        project,
        ctl,
        boundary_intents=intents,
        source_gain_db=args.source_gain_db,
        music_gain_db=args.music_gain_db,
    )
    write_model(Path(args.out), plan)
    j_count = sum(intent.kind == "j_cut" for intent in plan.boundaries)
    l_count = sum(intent.kind == "l_cut" for intent in plan.boundaries)
    print(f"Audio plan ready: {len(plan.events)} source event(s), {j_count} J-cut(s), {l_count} L-cut(s) -> {args.out}")


if __name__ == "__main__":
    main()
