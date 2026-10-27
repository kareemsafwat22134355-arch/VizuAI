from __future__ import annotations

import argparse
import json
from pathlib import Path

from .segmentation_backend_config import load_segmentation_backend_config
from .segmentation_backend_registry import (
    discover_segmentation_backends,
    validate_segmentation_backend_config,
)


def _print_json(payload: object) -> None:
    print(json.dumps(payload, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Discover optional segmentation backends and validate explicit local backend configuration"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="List allowlisted segmentation backends and installed runtime status")

    validate = subparsers.add_parser("validate", help="Validate one explicit segmentation backend config")
    validate.add_argument("--config", required=True)

    args = parser.parse_args()

    if args.command == "list":
        payload = {
            "backends": [
                backend.model_dump(by_alias=True, mode="json")
                for backend in discover_segmentation_backends()
            ],
            "notes": [
                "Backend discovery never installs packages or downloads model weights.",
                "Only allowlisted backends are recognized; arbitrary Python module paths are not supported.",
            ],
        }
        _print_json(payload)
        return

    config = load_segmentation_backend_config(Path(args.config))
    status = validate_segmentation_backend_config(config)
    _print_json({
        "config": config.model_dump(by_alias=True, mode="json"),
        "status": status.model_dump(by_alias=True, mode="json"),
    })
    raise SystemExit(0 if status.ready else 2)


if __name__ == "__main__":
    main()
