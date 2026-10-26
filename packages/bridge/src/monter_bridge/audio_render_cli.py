from __future__ import annotations

import argparse
from pathlib import Path

from .audio_mix_audit import audit_audio_mix
from .manifest_io import load_audio_edit_plan, load_ctl, load_project, write_model
from .render import render_draft


def main() -> None:
    parser = argparse.ArgumentParser(description="Render CTL with an explicit source-audio/J-L edit plan")
    parser.add_argument("--manifest", default=".monter/project.monter.json")
    parser.add_argument("--ctl", default=".monter/ctl.json")
    parser.add_argument("--audio-plan", default=".monter/audio-edit-plan.json")
    parser.add_argument("--proxy-dir", default=".monter/proxies")
    parser.add_argument("--music", default=None)
    parser.add_argument("--out", default=".monter/rough-cut.audio.mp4")
    parser.add_argument("--audit-out", default=".monter/audio-mix-audit.json")
    parser.add_argument("--safe-threshold-dbfs", type=float, default=-0.5)
    args = parser.parse_args()

    project = load_project(Path(args.manifest))
    ctl = load_ctl(Path(args.ctl))
    audio_plan = load_audio_edit_plan(Path(args.audio_plan))
    output = Path(args.out)
    render_draft(
        ctl,
        project,
        Path(args.proxy_dir),
        output,
        Path(args.music) if args.music else None,
        audio_plan=audio_plan,
    )

    audit = audit_audio_mix(output, safety_threshold_dbfs=args.safe_threshold_dbfs)
    write_model(Path(args.audit_out), audit)
    if not audit.clipping_safe:
        raise SystemExit(
            f"Audio-aware draft rendered but failed mix safety: max={audit.max_volume_dbfs:.1f} dBFS "
            f"> threshold={audit.safety_threshold_dbfs:.1f} dBFS. Audit -> {args.audit_out}"
        )

    print(
        f"Audio-aware draft rendered: {len(audio_plan.events)} source event(s), "
        f"{len(audio_plan.boundaries)} J/L boundary intent(s) | "
        f"max={audit.max_volume_dbfs:.1f} dBFS SAFE -> {args.out} | audit -> {args.audit_out}"
    )


if __name__ == "__main__":
    main()
