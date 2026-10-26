from __future__ import annotations

import argparse
from pathlib import Path

import orjson

from .ctl import compile_ctl
from .manifest_io import load_edit_plan, load_vir, write_model
from .transition_refinement_models import TransitionRefinementReport


def main() -> None:
    parser = argparse.ArgumentParser(description="Compile CTL with optional executed-flow transition refinement")
    parser.add_argument("--edit-plan", default=".monter/edit-plan.json")
    parser.add_argument("--vir", default=".monter/vir.monter.json")
    parser.add_argument("--refinement", default=".monter/transition-refinement.json")
    parser.add_argument("--fps", type=int, default=24)
    parser.add_argument("--width", type=int, default=960)
    parser.add_argument("--out", default=".monter/ctl.refined.json")
    args = parser.parse_args()

    edit_plan = load_edit_plan(Path(args.edit_plan))
    vir = load_vir(Path(args.vir))
    refinement = TransitionRefinementReport.model_validate(orjson.loads(Path(args.refinement).read_bytes()))
    ctl = compile_ctl(
        edit_plan,
        vir,
        fps=args.fps,
        width=args.width,
        transition_refinement=refinement,
    )
    write_model(Path(args.out), ctl)

    refined = sum(
        transition.evidence.get("advancedRefinementStatus") in {"confirmed", "demoted"}
        for transition in ctl.transitions
    )
    print(f"Refined CTL ready: {len(ctl.transitions)} boundaries, {refined} advanced decisions -> {args.out}")


if __name__ == "__main__":
    main()
