"""Fail early on unresolved Linux X11 plugin dependencies, without a display."""
import argparse
import json
import subprocess
import sys
from pathlib import Path


def inspect_x11(directory: Path | None = None) -> dict:
    if directory is None:
        import PySide6
        plugin = Path(PySide6.__file__).parent / "Qt/plugins/platforms/libqxcb.so"
    else:
        plugin = directory / "PySide6/qt-plugins/platforms/libqxcb.so"
    if not plugin.is_file():
        return {"plugin": str(plugin), "passed": False, "error": "X11 platform plugin is missing"}
    completed = subprocess.run(["ldd", str(plugin.resolve())], capture_output=True, text=True, timeout=30)
    output = completed.stdout + completed.stderr
    missing = sorted({line.strip().split()[0] for line in output.splitlines() if "=> not found" in line})
    return {"plugin": str(plugin), "passed": completed.returncode == 0 and not missing,
            "missing": missing, "returncode": completed.returncode, "loader_output": output}


def require_x11(directory: Path | None = None, *, output: Path | None = None) -> None:
    if sys.platform != "linux":
        return
    report = inspect_x11(directory)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if not report["passed"]:
        raise RuntimeError("Linux Qt/X11 dependency check failed:\n" + report.get("loader_output", report.get("error", "")))
    print("Linux Qt/X11 loader dependencies resolved: " + report["plugin"], flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, help="Inspect a compiled launch.dist directory instead of the build wheel")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    require_x11(args.directory, output=args.output)


if __name__ == "__main__":
    main()
