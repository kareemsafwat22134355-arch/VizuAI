from __future__ import annotations

import argparse
from pathlib import Path

import orjson

from .advanced_analysis_models import AdvancedAnalysisPlan
from .advanced_executor import execute_advanced_analysis
from .manifest_io import load_project, write_model


def main() -> None:
    parser = argparse.ArgumentParser(description="Execute scheduler-selected advanced analysis windows")
    parser.add_argument("--manifest", default=".monter/project.monter.json")
    parser.add_argument("--plan", default=".monter/advanced-analysis-plan.json")
    parser.add_argument("--proxy-dir", default=".monter/proxies")
    parser.add_argument("--sample-fps", type=float, default=12.0)
    parser.add_argument("--analysis-width", type=int, default=320)
    parser.add_argument("--out", default=".monter/advanced-analysis-results.json")
    args = parser.parse_args()

    project = load_project(Path(args.manifest))
    plan = AdvancedAnalysisPlan.model_validate(orjson.loads(Path(args.plan).read_bytes()))
    results = execute_advanced_analysis(
        project,
        plan,
        Path(args.proxy_dir),
        sample_fps=args.sample_fps,
        analysis_width=args.analysis_width,
    )
    write_model(Path(args.out), results)

    completed = sum(
        feature.status == "completed"
        for boundary in results.boundaries
        for feature in boundary.features
    )
    unavailable = sum(
        feature.status == "backend_unavailable"
        for boundary in results.boundaries
        for feature in boundary.features
    )
    failed = sum(
        feature.status == "failed"
        for boundary in results.boundaries
        for feature in boundary.features
    )
    print(
        f"Advanced analysis executed: {len(results.boundaries)} boundary request(s) | "
        f"completed={completed} unavailable={unavailable} failed={failed} -> {args.out}"
    )


if __name__ == "__main__":
    main()
