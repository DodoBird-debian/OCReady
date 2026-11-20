"""Verify the current standalone vision worker and all of its runtime files."""
import argparse
import json
import os
import re
import sys
from pathlib import Path

from scripts.provenance import file_sha256

ROOT = Path(__file__).resolve().parents[1]


def verify_worker(folder: Path, *, source_root: Path = ROOT, python_version: str | None = None) -> dict:
    folder = folder.resolve()
    marker = folder / "vision-build.json"
    if not marker.is_file() or marker.stat().st_size > 1_000_000:
        raise ValueError("The vision worker manifest is missing or too large.")
    data = json.loads(marker.read_text(encoding="utf-8"))
    inputs = {"entrypoint_sha256": "native/vision_bridge.py", "builder_sha256": "scripts/build_vision_bridge.py",
              "backend_errors_sha256": "ocready/core/backend_errors.py", "backend_probe_sha256": "ocready/core/backend_probe.py"}
    if (not isinstance(data, dict) or type(data.get("protocol")) is not int or data["protocol"] != 1
            or data.get("adapter") != "json-cli-v1" or data.get("python") != (python_version or sys.version.split()[0])
            or not isinstance(data.get("source"), dict) or data["source"].get("dirty") is not False
            or any(data.get(key) != file_sha256(source_root / relative) for key, relative in inputs.items())):
        raise ValueError("The vision worker does not match clean current source, builder, protocol or Python.")
    files = data.get("files")
    executable = "ocready-vision-bridge" + (".exe" if os.name == "nt" else "")
    native = "llama/llama-mtmd-cli" + (".exe" if os.name == "nt" else "")
    if (not isinstance(files, dict) or not files or executable not in files or native not in files
            or data.get("native_runner_sha256") != files[native]):
        raise ValueError("The vision worker inventory omits its executable or native runner identity.")
    for relative, digest in files.items():
        if not isinstance(relative, str):
            raise ValueError("Invalid vision worker inventory path.")
        path = Path(relative)
        target = folder / path
        if (path.is_absolute() or ".." in path.parts or ":" in relative or "\\" in relative
                or not target.resolve().is_relative_to(folder) or not target.is_file()
                or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)
                or file_sha256(target) != digest):
            raise ValueError(f"The vision worker inventory changed: {relative}")
    actual = {p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file() and p != marker}
    if actual != set(files):
        raise ValueError("The vision worker contains undeclared runtime files.")
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    args = parser.parse_args()
    try:
        verify_worker(args.folder)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        parser.exit(2, f"Vision worker verification failed: {exc}\n")
    print("Vision worker source, protocol, native runner and complete inventory verified.")


if __name__ == "__main__":
    main()
