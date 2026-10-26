from __future__ import annotations

import argparse
from pathlib import Path

import orjson

from .correction_models import CorrectionKind, CorrectionTargetType, DecisionScalar
from .corrections import append_correction
from .manifest_io import load_project


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


def main() -> None:
    parser = argparse.ArgumentParser(description="Record a human correction against a MONTER decision")
    parser.add_argument("--project-manifest", default=".monter/project.monter.json")
    parser.add_argument("--ledger", default=".monter/human-corrections.json")
    parser.add_argument("--kind", required=True, choices=["shot_selection", "trim", "transition", "timewarp", "role", "other"])
    parser.add_argument("--target-type", required=True, choices=["project", "segment", "boundary"])
    parser.add_argument("--target-ref", default=None, help="segment id or boundary index/reference; omit only for project-level corrections")
    parser.add_argument("--ai-json", required=True, help='AI decision as a flat JSON object, e.g. {"mechanism":"directional_bridge"}')
    parser.add_argument("--human-json", required=True, help='human replacement as a flat JSON object, e.g. {"mechanism":"hard_cut"}')
    parser.add_argument("--context-json", default="{}", help="optional flat JSON evidence snapshot")
    parser.add_argument("--reason", required=True)
    args = parser.parse_args()

    project = load_project(Path(args.project_manifest))
    ai_decision = _json_object(args.ai_json, "--ai-json")
    human_decision = _json_object(args.human_json, "--human-json")
    context = _json_object(args.context_json, "--context-json")

    ledger, correction = append_correction(
        Path(args.ledger),
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
        f"Correction recorded: {correction.id} | {correction.kind} | "
        f"{len(ledger.corrections)} correction(s) -> {args.ledger}"
    )


if __name__ == "__main__":
    main()
