from __future__ import annotations

import argparse
from pathlib import Path

from .manifest_io import load_microscope_report, write_model
from .microscope import aggregate_style_profile, inspect_finished_video


def microscope_main() -> None:
    parser = argparse.ArgumentParser(description="Reverse-engineer rhythm and motion decisions from a finished edit")
    parser.add_argument("video")
    parser.add_argument("--label", default=None, help="portable label stored instead of a local source path")
    parser.add_argument("--out", default="microscope-report.json")
    args = parser.parse_args()

    report = inspect_finished_video(Path(args.video), source_label=args.label)
    write_model(Path(args.out), report)
    print(
        f"Microscope ready: {report.shot_count} shots, {report.cut_count} cuts, "
        f"median shot {report.median_shot_duration_seconds:.2f}s -> {args.out}"
    )


def style_profile_main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate finished-edit microscope reports into a MONTER style prior")
    parser.add_argument("reports", nargs="+")
    parser.add_argument("--name", default="MONTER Style Profile")
    parser.add_argument("--out", default="style-profile.json")
    args = parser.parse_args()

    reports = [load_microscope_report(Path(path)) for path in args.reports]
    profile = aggregate_style_profile(reports, profile_name=args.name)
    write_model(Path(args.out), profile)
    print(
        f"Style profile ready: {profile.videos_analyzed} videos, {profile.cuts_analyzed} cuts, "
        f"confidence {profile.confidence:.2f} -> {args.out}"
    )
