from __future__ import annotations

import argparse
from pathlib import Path

import orjson

from .advanced_analysis import build_advanced_analysis_plan
from .manifest_io import load_ctl, write_model
from .transition_opportunities import TransitionOpportunityReport


def main() -> None:
    parser = argparse.ArgumentParser(description="Budget selective dense-flow/depth work around edit boundaries")
    parser.add_argument("--ctl", default=".monter/ctl.json")
    parser.add_argument("--opportunities", default=".monter/transition-opportunities.json")
    parser.add_argument("--max-boundaries", type=int, default=4)
    parser.add_argument("--out", default=".monter/advanced-analysis-plan.json")
    args = parser.parse_args()

    ctl = load_ctl(Path(args.ctl))
    opportunities = TransitionOpportunityReport.model_validate(orjson.loads(Path(args.opportunities).read_bytes()))
    plan = build_advanced_analysis_plan(ctl, opportunities, max_boundaries=args.max_boundaries)
    write_model(Path(args.out), plan)

    feature_counts: dict[str, int] = {}
    for request in plan.requests:
        for feature in request.requested_features:
            feature_counts[feature] = feature_counts.get(feature, 0) + 1
    summary = ", ".join(f"{name}={count}" for name, count in sorted(feature_counts.items())) or "no expensive analysis"
    print(f"Advanced analysis plan: {len(plan.requests)} boundary request(s) | {summary} -> {args.out}")


if __name__ == "__main__":
    main()
