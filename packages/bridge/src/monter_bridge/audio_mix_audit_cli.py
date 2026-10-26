from __future__ import annotations

import argparse
from pathlib import Path

from .audio_mix_audit import audit_audio_mix
from .manifest_io import write_model


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit decoded rendered audio peak/headroom after encode")
    parser.add_argument("input")
    parser.add_argument("--safe-threshold-dbfs", type=float, default=-0.5)
    parser.add_argument("--out", default=".monter/audio-mix-audit.json")
    args = parser.parse_args()

    report = audit_audio_mix(Path(args.input), safety_threshold_dbfs=args.safe_threshold_dbfs)
    write_model(Path(args.out), report)
    status = "SAFE" if report.clipping_safe else "HOT"
    print(
        f"Audio mix audit: {status} | max={report.max_volume_dbfs:.1f} dBFS | "
        f"mean={report.mean_volume_dbfs:.1f} dBFS | threshold={report.safety_threshold_dbfs:.1f} dBFS -> {args.out}"
    )
    if not report.clipping_safe:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
