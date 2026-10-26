from __future__ import annotations

import argparse
from pathlib import Path

import orjson

from .ingest import ingest_project


def main() -> None:
    parser = argparse.ArgumentParser(prog="monter", description="MONTER local media bridge")
    sub = parser.add_subparsers(dest="command", required=True)

    ingest = sub.add_parser("ingest", help="index a RAW footage folder without uploading it")
    ingest.add_argument("folder")
    ingest.add_argument("--name", default="MONTER Project")
    ingest.add_argument("--out", default="project.monter.json")

    args = parser.parse_args()
    if args.command == "ingest":
        project = ingest_project(Path(args.folder), args.name)
        portable = project.model_dump(by_alias=True)
        Path(args.out).write_bytes(orjson.dumps(portable, option=orjson.OPT_INDENT_2))
        print(f"Indexed {len(project.assets)} assets -> {args.out}")


if __name__ == "__main__":
    main()
