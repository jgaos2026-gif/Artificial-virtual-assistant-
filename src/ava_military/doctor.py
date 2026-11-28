"""Read-only installation diagnostics for the AVA research package.

This is a local package/environment doctor, not a security certification or
integrated OASIS runtime health check.
"""
from __future__ import annotations

import importlib.util
import json
import os
import platform
import shutil
import sys
from pathlib import Path
from typing import Any


def inspect_environment(source: str | Path | None = None, runtime: str | Path | None = None) -> dict[str, Any]:
    source_path = Path(source).expanduser().resolve() if source else None
    runtime_path = Path(runtime).expanduser().resolve() if runtime else None
    package_spec = importlib.util.find_spec("ava_military")
    checks = {
        "python_supported": sys.version_info >= (3, 11),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "package_importable": package_spec is not None,
        "git_available": shutil.which("git") is not None,
        "source_exists": source_path.is_dir() if source_path else None,
        "source_pyproject_exists": (source_path / "pyproject.toml").is_file() if source_path else None,
        "runtime_exists": runtime_path.is_dir() if runtime_path else None,
        "runtime_writable": os.access(runtime_path, os.W_OK) if runtime_path and runtime_path.exists() else None,
    }
    blockers = []
    if not checks["python_supported"]:
        blockers.append("Python 3.11 or newer is required.")
    if not checks["package_importable"]:
        blockers.append("ava_military is not importable in this interpreter.")
    if source_path and not checks["source_pyproject_exists"]:
        blockers.append("Source path does not contain pyproject.toml.")
    return {
        "classification": "FOUNDATION_DIAGNOSTICS_ONLY",
        "checks": checks,
        "blockers": blockers,
        "integrated_runtime": "NOT_IMPLEMENTED",
        "production_security": "NOT_ASSESSED",
        "network_policy_enforcement": "NOT_ASSESSED",
        "external_anchor_and_sb712_quorum": "NOT_IMPLEMENTED",
        "backup_restore_drill": "NOT_RUN",
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Read-only AVA research foundation doctor")
    parser.add_argument("--source")
    parser.add_argument("--runtime")
    args = parser.parse_args()
    report = inspect_environment(args.source, args.runtime)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if not report["blockers"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
