"""Validate a reusable compiled worker against current sources and dependencies."""
import argparse
import importlib.metadata
import json
import os
import re
import sys
from pathlib import Path

from scripts.build_neural_runner import ROOT, WORKER_PACKAGES
from scripts.provenance import file_sha256


def verify_worker(folder: Path, *, source_root: Path = ROOT, dependencies: dict | None = None,
                  python_version: str | None = None) -> None:
    folder = folder.resolve()
    marker = folder / "neural-build.json"
    if not marker.is_file() or marker.stat().st_size > 1_000_000:
        raise ValueError("The compiled worker manifest is missing or too large.")
    metadata = json.loads(marker.read_text(encoding="utf-8"))
    versions = dependencies if dependencies is not None else {name: importlib.metadata.version(name) for name in WORKER_PACKAGES}
    source_record = metadata.get("source") if isinstance(metadata, dict) else None
    if (not isinstance(metadata, dict) or type(metadata.get("protocol")) is not int or metadata["protocol"] != 1
            or metadata.get("entrypoint_sha256") != file_sha256(source_root / "native/neural_runner.py")
            or metadata.get("builder_sha256") != file_sha256(source_root / "scripts/build_neural_runner.py")
            or metadata.get("dependencies") != versions
            or metadata.get("python") != (python_version or sys.version.split()[0])
            or not isinstance(source_record, dict) or source_record.get("dirty") is not False):
        raise ValueError("The compiled worker does not match current source, builder, Python or dependencies.")
    files = metadata.get("files")
    executable = "ocready-neural-runner.exe" if os.name == "nt" else "ocready-neural-runner"
    if not isinstance(files, dict) or not files or executable not in files:
        raise ValueError("The compiled worker file inventory is incomplete.")
    for relative, digest in files.items():
        path = Path(relative)
        source = folder / path
        if (path.is_absolute() or ".." in path.parts or ":" in relative or "\\" in relative
                or not source.resolve().is_relative_to(folder) or not isinstance(digest, str)
                or not re.fullmatch(r"[0-9a-f]{64}", digest) or not source.is_file() or file_sha256(source) != digest):
            raise ValueError(f"The compiled worker inventory changed: {relative}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    args = parser.parse_args()
    try:
        verify_worker(args.folder)
    except (OSError, ValueError, TypeError, KeyError, importlib.metadata.PackageNotFoundError) as exc:
        parser.exit(2, f"Compiled worker verification failed: {exc}\n")
    print("Compiled worker source, runtime and declared files verified.")


if __name__ == "__main__":
    main()
