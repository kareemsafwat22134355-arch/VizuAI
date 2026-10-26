from __future__ import annotations

import argparse
from pathlib import Path

import orjson

from .advanced_execution_models import AdvancedAnalysisResults
from .manifest_io import write_model
from .transition_opportunities import TransitionOpportunityReport
from .transition_refinement import refine_transition_opportunities


def main() -> None:
    parser = argparse.ArgumentParser(description="Refine transition recommendations using executed advanced-analysis evidence")
    parser.add_argument("--opportunities", default=".monter/transition-opportunities.json")
    parser.add_argument("--results", default=".monter/advanced-analysis-results.json")
    parser.add_argument("--out", default=".monter/transition-refinement.json")
    args = parser.parse_args()

    opportunities = TransitionOpportunityReport.model_validate(orjson.loads(Path(args.opportunities).read_bytes()))
    results = AdvancedAnalysisResults.model_validate(orjson.loads(Path(args.results).read_bytes()))
    report = refine_transition_opportunities(opportunities, results)
    write_model(Path(args.out), report)

    confirmed = sum(item.status == "confirmed" for item in report.boundaries)
    demoted = sum(item.status == "demoted" for item in report.boundaries)
    unresolved = sum(item.status == "unresolved" for item in report.boundaries)
    print(
        f"Transition refinement: {confirmed} confirmed, {demoted} demoted, "
        f"{unresolved} unresolved -> {args.out}"
    )


if __name__ == "__main__":
    main()
