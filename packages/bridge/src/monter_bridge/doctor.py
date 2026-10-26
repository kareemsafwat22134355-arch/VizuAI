from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


def _binary_status(name: str) -> dict[str, object]:
    path = shutil.which(name)
    if path is None:
        return {"name": name, "ok": False, "path": None, "version": None}

    version: str | None = None
    try:
        completed = subprocess.run(
            [path, "-version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
        first_line = (completed.stdout or completed.stderr).splitlines()
        version = first_line[0] if first_line else None
    except (OSError, subprocess.SubprocessError):
        pass

    return {"name": name, "ok": True, "path": path, "version": version}


def doctor_report(work_dir: Path | None = None) -> dict[str, object]:
    python_ok = sys.version_info >= (3, 11)
    binaries = [_binary_status("ffmpeg"), _binary_status("ffprobe")]

    writable: bool | None = None
    if work_dir is not None:
        try:
            work_dir.mkdir(parents=True, exist_ok=True)
            probe = work_dir / ".monter-write-test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            writable = True
        except OSError:
            writable = False

    checks_ok = python_ok and all(bool(item["ok"]) for item in binaries)
    if writable is False:
        checks_ok = False

    return {
        "ok": checks_ok,
        "python": {
            "ok": python_ok,
            "version": ".".join(map(str, sys.version_info[:3])),
            "minimum": "3.11",
        },
        "binaries": binaries,
        "workDirWritable": writable,
        "profile": {
            "targetRamGb": 8,
            "strategy": "proxy-first progressive analysis",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Check whether this machine can run the MONTER local bridge")
    parser.add_argument("--work-dir", default=None)
    args = parser.parse_args()

    report = doctor_report(Path(args.work_dir) if args.work_dir else None)
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
