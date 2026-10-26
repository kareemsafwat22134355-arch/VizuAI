from __future__ import annotations

import argparse
from pathlib import Path

from .manifest_io import load_director_plan, load_project, write_model
from .render_analysis import analyze_render


def main() -> None:
    parser = argparse.ArgumentParser(description="Re-analyze the encoded final render for physical integrity and energy shape")
    parser.add_argument("--manifest", default=".monter/project.monter.json")
    parser.add_argument("--director-plan", default=".monter/director-plan.json")
    parser.add_argument("--render", default=".monter/rough-cut.mp4")
    parser.add_argument("--expected-duration", type=float, default=None, help="override expected timeline duration")
    parser.add_argument("--sample-fps", type=float, default=4.0)
    parser.add_argument("--analysis-width", type=int, default=320)
    parser.add_argument("--out", default=".monter/render-analysis.json")
    args = parser.parse_args()

    project = load_project(Path(args.manifest))
    director = load_director_plan(Path(args.director_plan))
    expected_duration = args.expected_duration if args.expected_duration is not None else director.target_duration_seconds
    report = analyze_render(
        Path(args.render),
        project_id=project.project_id,
        expected_duration_seconds=expected_duration,
        director_plan=director,
        sample_fps=args.sample_fps,
        analysis_width=args.analysis_width,
    )
    write_model(Path(args.out), report)
    print(
        f"Render re-analysis {report.status}: drift={report.duration_drift_seconds:+.3f}s, "
        f"black={report.black_frame_fraction:.1%}, freeze={report.longest_freeze_seconds:.2f}s, "
        f"energyAlignment={report.energy_alignment:.1%} -> {args.out}"
    )


if __name__ == "__main__":
    main()
