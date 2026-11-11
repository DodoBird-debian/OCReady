"""Compile the isolated neural worker with its numerical libraries, without Qt."""
import argparse
import importlib.metadata
import json
import os
import shutil
import subprocess
import sys
import sysconfig
from pathlib import Path

from scripts.provenance import file_sha256, require_unchanged, source_record

ROOT = Path(__file__).resolve().parents[1]
WORKER_PACKAGES = ("rapidocr", "onnxruntime", "opencv-python-headless", "numpy", "python-bidi", "Pillow", "shapely", "pyclipper", "omegaconf", "PyYAML")


def collect_notices(distribution: Path, packages) -> None:
    notices = distribution / "notices"
    for name in (*packages, "Nuitka", "requests", "python-dateutil", "six", "tqdm", "packaging", "certifi",
                 "charset-normalizer", "idna", "urllib3", "protobuf", "antlr4-python3-runtime"):
        try:
            package_metadata = importlib.metadata.distribution(name)
        except importlib.metadata.PackageNotFoundError:
            continue
        for file in package_metadata.files or []:
            if any(token in file.name.lower() for token in ("license", "copying", "copyright", "notice")):
                source = Path(package_metadata.locate_file(file))
                if source.is_file():
                    target = notices / name / file.name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if target.exists() and file_sha256(target) != file_sha256(source):
                        target = target.with_name(file_sha256(source)[:12] + "-" + target.name)
                    shutil.copyfile(source, target)
    candidates = (Path(sys.base_prefix) / "LICENSE.txt", Path(sysconfig.get_path("stdlib")) / "LICENSE.txt")
    python_license = next((path for path in candidates if path.is_file()), None)
    if not python_license:
        raise RuntimeError("The Python distribution's LICENSE.txt is missing; retain it before packaging the worker.")
    (notices / "Python").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(python_license, notices / "Python/LICENSE.txt")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jobs", type=int, default=2)
    args = parser.parse_args()
    source = source_record(ROOT)
    packages = WORKER_PACKAGES
    versions = {name: importlib.metadata.version(name) for name in packages}
    entrypoint = ROOT / "native/neural_runner.py"
    digest = file_sha256(entrypoint)
    package = Path(importlib.metadata.distribution("rapidocr").locate_file("rapidocr"))
    out = ROOT / "runtime/neural-runner/cpu"
    name = "ocready-neural-runner" + (".exe" if os.name == "nt" else "")
    command = [sys.executable, "-m", "nuitka", str(entrypoint), "--mode=standalone", "--lto=no",
               f"--jobs={args.jobs}", "--assume-yes-for-downloads", f"--output-dir={out}", f"--output-filename={name}",
               "--include-module=rapidocr.main", "--include-module=rapidocr.inference_engine.onnxruntime.main",
               "--nofollow-import-to=PySide6,torch,paddle,openvino,tensorrt,MNN,pytest,ruff",
               f"--include-data-files={package / 'config.yaml'}=rapidocr/config.yaml",
               f"--include-data-files={package / 'default_models.yaml'}=rapidocr/default_models.yaml",
               "--report=" + str(out / "compilation-report.xml")]
    if os.name == "nt":
        command += ["--windows-console-mode=attach"]
    env = os.environ.copy()
    env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")
    subprocess.run(command, cwd=ROOT, env=env, check=True)
    if file_sha256(entrypoint) != digest:
        raise RuntimeError("The worker entrypoint changed during compilation; rebuild it.")
    distribution = out / "neural_runner.dist"
    collect_notices(distribution, packages)
    require_unchanged(ROOT, source)
    metadata = {"source": source, "entrypoint_sha256": digest, "dependencies": versions,
                "builder_sha256": file_sha256(Path(__file__)),
                "backend_errors_sha256": file_sha256(ROOT / "ocready/core/backend_errors.py"),
                "protocol": 1, "model_family": "PP-OCRv5", "python": sys.version.split()[0],
                "files": {file.relative_to(distribution).as_posix(): file_sha256(file) for file in sorted(distribution.rglob("*"))
                          if file.is_file() and file.relative_to(distribution).as_posix() != "neural-build.json"}}
    (distribution / "neural-build.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(distribution / ("ocready-neural-runner.exe" if os.name == "nt" else "ocready-neural-runner"))


if __name__ == "__main__":
    main()
