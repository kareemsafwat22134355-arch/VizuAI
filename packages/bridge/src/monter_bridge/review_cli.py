from __future__ import annotations

import argparse
from pathlib import Path

import orjson

from .correction_models import DecisionScalar
from .corrections import load_correction_ledger
from .manifest_io import load_project, write_model
from .reviews import (
    build_review_summary,
    load_review_ledger,
    record_accepted_review,
    record_corrected_review,
)


def _json_object(value: str, label: str) -> dict[str, DecisionScalar]:
    try:
        parsed = orjson.loads(value)
    except orjson.JSONDecodeError as exc:
        raise argparse.ArgumentTypeError(f"{label} must be valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise argparse.ArgumentTypeError(f"{label} must be a JSON object")
    for key, item in parsed.items():
        if not isinstance(key, str) or not (item is None or isinstance(item, (str, int, float, bool))):
            raise argparse.ArgumentTypeError(f"{label} values must be scalar JSON values")
    return parsed


def review_main() -> None:
    parser = argparse.ArgumentParser(description="Record the result of a human review of a MONTER decision")
    parser.add_argument("--project-manifest", default=".monter/project.monter.json")
    parser.add_argument("--reviews", default=".monter/decision-reviews.json")
    parser.add_argument("--corrections", default=".monter/human-corrections.json")
    parser.add_argument("--kind", required=True, choices=["shot_selection", "trim", "transition", "timewarp", "role", "other"])
    parser.add_argument("--target-type", required=True, choices=["project", "segment", "boundary"])
    parser.add_argument("--target-ref", default=None)
    parser.add_argument("--outcome", required=True, choices=["accepted", "corrected"])
    parser.add_argument("--ai-json", required=True, help="AI decision as a flat JSON object")
    parser.add_argument("--human-json", default=None, help="required only when --outcome corrected")
    parser.add_argument("--context-json", default="{}", help="optional flat JSON context/evidence snapshot")
    parser.add_argument("--reason", default=None)
    args = parser.parse_args()

    project = load_project(Path(args.project_manifest))
    ai_decision = _json_object(args.ai_json, "--ai-json")
    context = _json_object(args.context_json, "--context-json")

    if args.outcome == "accepted":
        if args.human_json is not None:
            parser.error("--human-json is only valid for corrected reviews")
        reviews, review = record_accepted_review(
            Path(args.reviews),
            project.project_id,
            kind=args.kind,
            target_type=args.target_type,
            target_ref=args.target_ref,
            ai_decision=ai_decision,
            context=context,
            reason=args.reason or "Accepted as-is.",
            source="cli",
        )
        print(f"Decision accepted: {review.id} | {len(reviews.reviews)} reviewed decision(s) -> {args.reviews}")
        return

    if args.human_json is None:
        parser.error("--human-json is required when --outcome corrected")
    if not args.reason:
        parser.error("--reason is required when --outcome corrected")
    human_decision = _json_object(args.human_json, "--human-json")
    reviews, corrections, review = record_corrected_review(
        Path(args.reviews),
        Path(args.corrections),
        project.project_id,
        kind=args.kind,
        target_type=args.target_type,
        target_ref=args.target_ref,
        ai_decision=ai_decision,
        human_decision=human_decision,
        context=context,
        reason=args.reason,
        source="cli",
    )
    print(
        f"Decision corrected: {review.id} -> {review.correction_id} | "
        f"{len(reviews.reviews)} review(s), {len(corrections.corrections)} correction(s)"
    )


def summary_main() -> None:
    parser = argparse.ArgumentParser(description="Summarize reviewed MONTER decisions with truthful acceptance denominators")
    parser.add_argument("--reviews", default=".monter/decision-reviews.json")
    parser.add_argument("--corrections", default=".monter/human-corrections.json")
    parser.add_argument("--out", default=".monter/decision-review-summary.json")
    args = parser.parse_args()

    reviews = load_review_ledger(Path(args.reviews))
    correction_path = Path(args.corrections)
    corrections = load_correction_ledger(correction_path) if correction_path.exists() else None
    summary = build_review_summary(reviews, corrections)
    write_model(Path(args.out), summary)
    print(
        f"Review summary: {summary.reviewed} reviewed | {summary.accepted} accepted | "
        f"{summary.corrected} corrected | acceptance {summary.acceptance_rate:.1%} -> {args.out}"
    )


if __name__ == "__main__":
    review_main()
