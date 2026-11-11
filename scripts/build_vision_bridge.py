"""Compile a standalone JSON v1 reference worker with a selected native runner."""
import argparse
import json
import os
import shutil
import subprocess
import sys
import sysconfig
from pathlib import Path

from scripts.provenance import file_sha256, require_unchanged, source_record

ROOT = Path(__file__).resolve().parents[1]


def copy_runtime(runner: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True, exist_ok=True)
    files = {runner, *runner.parent.glob("*.dll"), *runner.parent.glob("*.so*")}
    libdir = runner.parent.parent / "lib"
    if libdir.is_dir():
        files.update(libdir.glob("*.so*"))
    copied = {}
    for source in sorted(files):
        if source.is_file():
            target = destination / source.name
            stat = source.stat()
            identity = (stat.st_dev, stat.st_ino)
            if identity in copied:
                try:
                    target.hardlink_to(copied[identity])
                except OSError:
                    shutil.copy2(source, target)
            else:
                shutil.copy2(source, target)
                copied[identity] = target
    for pattern in ("LICENSE*", "NOTICE*", "COPYING*"):
        for source in runner.parent.glob(pattern):
            if source.is_file():
                shutil.copy2(source, destination / source.name)
    if (runner.parent / "notices").is_dir():
        shutil.copytree(runner.parent / "notices", destination / "notices", dirs_exist_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runner", type=Path, required=True, help="A compatible llama-mtmd-cli to include with the bridge")
    parser.add_argument("--output", type=Path, default=ROOT / "runtime/vision-bridge/cpu")
    parser.add_argument("--jobs", type=int, default=2)
    args = parser.parse_args()
    runner = args.runner.resolve()
    if not runner.is_file():
        parser.error("Choose an existing native multimodal runner.")
    source = source_record(ROOT)
    entrypoint = ROOT / "native/vision_bridge.py"
    output = args.output.resolve()
    name = "ocready-vision-bridge" + (".exe" if os.name == "nt" else "")
    command = [sys.executable, "-m", "nuitka", str(entrypoint), "--mode=standalone", "--lto=no",
               "--assume-yes-for-downloads", f"--jobs={args.jobs}", f"--output-dir={output}", f"--output-filename={name}",
               "--nofollow-import-to=PySide6,PIL,numpy,torch,pytest,ruff", "--report=" + str(output / "compilation-report.xml")]
    if os.name == "nt":
        command += ["--windows-console-mode=attach"]
    env = os.environ.copy()
    env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")
    subprocess.run(command, cwd=ROOT, env=env, check=True)
    distribution = output / "vision_bridge.dist"
    copy_runtime(runner, distribution / "llama")
    license_file = next((p for p in (Path(sys.base_prefix) / "LICENSE.txt", Path(sysconfig.get_path("stdlib")) / "LICENSE.txt") if p.is_file()), None)
    if not license_file:
        raise RuntimeError("Retain the Python distribution's LICENSE.txt before packaging this worker.")
    shutil.copy2(license_file, distribution / "LICENSE-Python.txt")
    shutil.copy2(ROOT / "LICENSE", distribution / "LICENSE-OCReady.txt")
    require_unchanged(ROOT, source)
    metadata = {"protocol": 1, "adapter": "json-cli-v1", "source": source,
                "entrypoint_sha256": file_sha256(entrypoint), "python": sys.version.split()[0],
                "native_runner_sha256": file_sha256(distribution / "llama" / runner.name),
                "files": {p.relative_to(distribution).as_posix(): file_sha256(p) for p in sorted(distribution.rglob("*"))
                          if p.is_file() and p.name != "vision-build.json"}}
    (distribution / "vision-build.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(distribution / name)


if __name__ == "__main__":
    main()
