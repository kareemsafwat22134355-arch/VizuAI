from __future__ import annotations

import argparse
from pathlib import Path

from .manifest_io import load_edit_plan, load_vir, write_model
from .transition_opportunities import synthesize_transition_opportunities


def main() -> None:
    parser = argparse.ArgumentParser(description="Synthesize motivated transition opportunities from an edit plan and VIR")
    parser.add_argument("--edit-plan", default=".monter/edit-plan.json")
    parser.add_argument("--vir", default=".monter/vir.monter.json")
    parser.add_argument("--out", default=".monter/transition-opportunities.json")
    args = parser.parse_args()

    edit_plan = load_edit_plan(Path(args.edit_plan))
    vir = load_vir(Path(args.vir))
    report = synthesize_transition_opportunities(edit_plan, vir)
    write_model(Path(args.out), report)

    bridge_count = sum(
        boundary.recommended_mechanism in {"directional_bridge", "zoom_bridge"}
        for boundary in report.boundaries
    )
    print(
        f"Transition opportunities ready: {len(report.boundaries)} boundaries, "
        f"{bridge_count} non-zero bridge recommendation(s) -> {args.out}"
    )


if __name__ == "__main__":
    main()
