from __future__ import annotations

import argparse
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

BUNDLE_VERSION = "monter-bundle-0.1"

CORE_ARTIFACTS = (
    "project.monter.json",
    "vir.monter.json",
    "director-plan.json",
    "edit-plan.json",
    "ctl.json",
    "critic-report.json",
    "transition-opportunities.json",
    "production-report.json",
    "audio-analysis.json",
    "edit.otio",
)

OPTIONAL_PREVIEW_ARTIFACTS = (
    "rough-cut.mp4",
)


def collect_bundle_artifacts(work_dir: Path, include_preview: bool = True) -> list[Path]:
    names = list(CORE_ARTIFACTS)
    if include_preview:
        names.extend(OPTIONAL_PREVIEW_ARTIFACTS)
    return [work_dir / name for name in names if (work_dir / name).is_file()]


def create_share_bundle(work_dir: Path, output: Path, include_preview: bool = True) -> dict[str, object]:
    work_dir = work_dir.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    required = work_dir / "project.monter.json"
    if not required.is_file():
        raise FileNotFoundError(f"Missing project manifest: {required}")

    artifacts = collect_bundle_artifacts(work_dir, include_preview=include_preview)
    manifest = {
        "schemaVersion": BUNDLE_VERSION,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "includedArtifacts": [path.name for path in artifacts],
        "rawMediaIncluded": False,
        "proxiesIncluded": False,
        "notes": [
            "RAW source media is intentionally excluded.",
            "Analysis proxies are intentionally excluded from the share bundle.",
            "All source references inside the project manifest are relative paths.",
        ],
    }

    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("bundle-manifest.json", json.dumps(manifest, indent=2))
        for artifact in artifacts:
            archive.write(artifact, arcname=artifact.name)

    manifest["bundleBytes"] = output.stat().st_size
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a portable MONTER analysis bundle without RAW media")
    parser.add_argument("work_dir", nargs="?", default=".monter")
    parser.add_argument("--out", default="project.monter.zip")
    parser.add_argument("--no-preview", action="store_true", help="exclude rough-cut preview video")
    args = parser.parse_args()

    result = create_share_bundle(
        Path(args.work_dir),
        Path(args.out),
        include_preview=not args.no_preview,
    )
    print(
        f"Bundle ready -> {args.out} | {len(result['includedArtifacts'])} artifacts | "
        f"{result['bundleBytes']} bytes"
    )


if __name__ == "__main__":
    main()
