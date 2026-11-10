"""Compile a Linux / Windows onefile executable with a selected OCR edition."""
import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--edition", choices=("pocket", "everyday", "studio"), default="pocket")
    parser.add_argument("--methods", help="Comma-separated fast,best,vision; defaults depend on edition")
    parser.add_argument("--model-pack", type=Path, action="append", default=[], help="Embed a local model manifest and its runner/weights; repeat for multiple packs")
    parser.add_argument("--standalone", action="store_true", help="Diagnostic directory build instead of onefile")
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    defaults = {"pocket": ["fast"], "everyday": ["fast", "best", "vision"], "studio": ["fast", "best", "vision"]}
    methods = args.methods.split(",") if args.methods else defaults[args.edition]
    if not methods or not set(methods) <= set(defaults[args.edition]):
        parser.error("Methods must be a nonempty subset of the edition's supported methods.")
    if not {"fast", "best"}.intersection(methods) and not args.model_pack:
        parser.error("A vision-only build needs at least one --model-pack to work offline.")
    if args.model_pack and "vision" not in methods:
        parser.error("Embedding model packs requires vision in --methods.")
    from ocready.core.editions import edition_for
    from ocready.core.models import load_pack
    from scripts.bundle_models import bundle_pack
    packs = [load_pack(path.resolve()) for path in args.model_pack]
    if len({pack.id for pack in packs}) != len(packs):
        parser.error("Embedded model IDs must be unique.")
    for pack in packs:
        pack.validate()
        allowed, reason = pack.admission(edition_for(args.edition))
        if not allowed:
            parser.error(reason)
    runtime = ROOT / "runtime"
    for quality in set(methods).intersection({"fast", "best"}):
        for language in ("ara", "eng"):
            if not (runtime / "tessdata" / quality / f"{language}.traineddata").exists():
                parser.error(f"Prepare {quality} data first: python scripts/prepare_runtime.py --best")
    platform_name = "windows" if os.name == "nt" else "linux"
    name = f"OCReady-{args.edition}-{platform_name}-{platform.machine().lower()}"
    stage = ROOT / "build" / args.edition / "payload"
    stage.mkdir(parents=True, exist_ok=True)
    bundle = stage / "runtime-bundle.tar.gz"
    # Binaries are packed as an archive, then safely extracted by the app. They are
    # executable assets, not Python modules or DLLs for Nuitka to import or patch.
    with tarfile.open(bundle, "w:gz", compresslevel=6) as archive:
        for folder in (["bin", "lib", "notices"] if {"fast", "best"}.intersection(methods) else ["notices"]):
            for path in sorted((runtime / folder).rglob("*")):
                if path.is_file():
                    archive.add(path.resolve(), arcname=str(path.relative_to(runtime)), recursive=False)
        for quality in set(methods).intersection({"fast", "best"}):
            for path in sorted((runtime / "tessdata" / quality).glob("*.traineddata")):
                archive.add(path, arcname=str(path.relative_to(runtime)), recursive=False)
        if (runtime / "manifest.json").exists():
            archive.add(runtime / "manifest.json", arcname="manifest.json", recursive=False)
        embedded = [bundle_pack(archive, pack) for pack in packs]
    editions = [args.edition]
    profile = {"edition": args.edition, "available_editions": editions,
               "methods": [f"tesseract-{m}" if m in {"fast", "best"} else m for m in methods],
               "platform": platform.platform(), "python": platform.python_version(),
               "embedded_models": embedded, "default_model": packs[0].id if packs else "",
               "runtime_bundle_sha256": hashlib.sha256(bundle.read_bytes()).hexdigest(),
               "memory_certification": "Uncertified; see docs/PROGRESS.md and benchmark evidence"}
    manifest = stage / "build-manifest.json"
    manifest.write_text(json.dumps(profile, indent=2) + "\n")
    out = ROOT / "dist" / args.edition
    out.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, "-m", "nuitka", str(ROOT / "launch.py"),
               "--mode=" + ("standalone" if args.standalone else "onefile"),
               "--enable-plugin=pyside6", "--include-qt-plugins=sensible,platforms,imageformats",
               "--assume-yes-for-downloads", "--lto=no", f"--jobs={args.jobs}",
               f"--output-dir={out}", f"--output-filename={name}" + (".exe" if os.name == "nt" else ""),
               f"--include-data-files={bundle}=runtime-bundle.tar.gz",
               f"--include-data-files={manifest}=build-manifest.json",
               f"--include-data-dir={ROOT / 'assets'}=assets",
               f"--include-data-dir={ROOT / 'docs'}=docs",
               f"--include-data-files={ROOT / 'LICENSE'}=LICENSE",
               "--noinclude-qt-translations", "--nofollow-import-to=pytest,ruff,PySide6.QtTest",
               "--report=" + str(out / "compilation-report.xml")]
    if os.name == "nt":
        command += ["--windows-console-mode=attach", "--company-name=OCReady", "--product-name=OCReady",
                    "--file-version=0.1.0.0", "--product-version=0.1.0.0"]
    env = os.environ.copy()
    env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")
    subprocess.run(command, cwd=ROOT, env=env, check=True)
    extension = ".exe" if os.name == "nt" else ""
    artifact = out / (name + extension)
    if artifact.exists():
        digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        artifact.with_suffix(artifact.suffix + ".sha256").write_text(f"{digest}  {artifact.name}\n")
        print(f"Built {artifact} ({artifact.stat().st_size / 1_000_000:.1f} MB)")
    shutil.copy2(manifest, out / "build-manifest.json")


if __name__ == "__main__":
    main()
