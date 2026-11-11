"""Compile a Linux / Windows onefile executable with a selected OCR edition."""
import argparse
import importlib.metadata
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
from datetime import UTC, datetime
from pathlib import Path

from scripts.payload_memory import compiler_overlay, overlay_environment
from scripts.provenance import file_sha256, included_runtime_manifest, require_unchanged, source_record

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--edition", choices=("pocket", "everyday", "studio"), default="pocket")
    parser.add_argument("--methods", help="Comma-separated fast,best,vision,neural; defaults depend on edition")
    parser.add_argument("--model-pack", type=Path, action="append", default=[], help="Embed a local model manifest and its runner/weights; repeat for multiple packs")
    parser.add_argument("--neural-pack", type=Path, action="append", default=[], help="Embed a neural OCR worker, models and dictionary")
    parser.add_argument("--variant", default="", help="Optional short artifact variant name, e.g. neural or multimodal")
    parser.add_argument("--standalone", action="store_true", help="Diagnostic directory build instead of onefile")
    parser.add_argument("--no-payload-trim", action="store_true", help="Diagnostic build without releasing unused launcher pages")
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    source = source_record(ROOT)
    defaults = {"pocket": ["fast"], "everyday": ["fast", "best", "vision", "neural"], "studio": ["fast", "best", "vision", "neural"]}
    if args.variant and not re.fullmatch(r"[a-z0-9_-]{1,30}", args.variant):
        parser.error("Variant names use 1–30 lowercase letters, digits, underscores or hyphens.")
    methods = args.methods.split(",") if args.methods else defaults[args.edition]
    if not methods or not set(methods) <= set(defaults[args.edition]):
        parser.error("Methods must be a nonempty subset of the edition's supported methods.")
    if not {"fast", "best"}.intersection(methods) and not (args.model_pack or args.neural_pack):
        parser.error("A local-model-only build needs at least one --model-pack or --neural-pack.")
    if methods[0] == "vision" and not args.model_pack or methods[0] == "neural" and not args.neural_pack:
        parser.error("The default method must have an embedded pack so the build works offline.")
    if args.model_pack and "vision" not in methods:
        parser.error("Embedding model packs requires vision in --methods.")
    if args.neural_pack and "neural" not in methods:
        parser.error("Embedding neural packs requires neural in --methods.")
    from ocready.core.editions import edition_for
    from ocready.core.models import load_pack
    from ocready.core.neural_packs import load_neural_pack
    from scripts.bundle_models import bundle_neural_pack, bundle_pack
    packs = [load_pack(path.resolve()) for path in args.model_pack]
    neural_packs = [load_neural_pack(path.resolve()) for path in args.neural_pack]
    if len({pack.id for pack in packs}) != len(packs) or len({pack.id for pack in neural_packs}) != len(neural_packs):
        parser.error("Embedded model IDs must be unique.")
    for pack in [*packs, *neural_packs]:
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
    variant = args.edition + ("-" + args.variant if args.variant else "")
    name = f"OCReady-{variant}-{platform_name}-{platform.machine().lower()}"
    stage = ROOT / "build" / variant / "payload"
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
            for language in ("ara", "eng"):
                path = runtime / "tessdata" / quality / f"{language}.traineddata"
                archive.add(path, arcname=str(path.relative_to(runtime)), recursive=False)
        gate = runtime / "bin" / "ocready-exec-gate"
        if not {"fast", "best"}.intersection(methods) and gate.is_file():
            archive.add(gate, arcname="bin/ocready-exec-gate", recursive=False)
        embedded = [bundle_pack(archive, pack) for pack in packs]
        embedded_neural = [bundle_neural_pack(archive, pack) for pack in neural_packs]
        if (runtime / "manifest.json").exists():
            selected_manifest = stage / "runtime-manifest.json"
            selected_manifest.write_text(json.dumps(included_runtime_manifest(runtime, set(archive.getnames())), indent=2), encoding="utf-8")
            archive.add(selected_manifest, arcname="manifest.json", recursive=False)
    editions = [args.edition]
    profile = {"edition": args.edition, "available_editions": editions,
               "methods": [f"tesseract-{m}" if m in {"fast", "best"} else m for m in methods],
               "platform": platform.platform(), "python": platform.python_version(),
               "embedded_models": embedded, "default_model": packs[0].id if packs else "",
               "embedded_neural": embedded_neural, "default_neural": neural_packs[0].id if neural_packs else "", "variant": args.variant,
               "runtime_bundle_sha256": file_sha256(bundle),
               "source": source, "built_at_utc": datetime.now(UTC).isoformat(),
               "dependencies": {name: importlib.metadata.version(name) for name in ("Nuitka", "Pillow", "psutil", "PySide6-Essentials")},
               "memory_certification": "Uncertified; see docs/PROGRESS.md and benchmark evidence"}
    manifest = stage / "build-manifest.json"
    manifest.write_text(json.dumps(profile, indent=2) + "\n")
    out = ROOT / "dist" / variant
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
    with compiler_overlay(stage.parent, enabled=not args.standalone and not args.no_payload_trim) as (overlay, metadata):
        profile["payload_memory"] = metadata
        manifest.write_text(json.dumps(profile, indent=2) + "\n", encoding="utf-8")
        subprocess.run(command, cwd=ROOT, env=overlay_environment(env, overlay), check=True)
    require_unchanged(ROOT, source)
    extension = ".exe" if os.name == "nt" else ""
    artifact = out / (name + extension)
    if artifact.exists():
        digest = file_sha256(artifact)
        artifact.with_suffix(artifact.suffix + ".sha256").write_text(f"{digest}  {artifact.name}\n")
        print(f"Built {artifact} ({artifact.stat().st_size / 1_000_000:.1f} MB)")
    shutil.copy2(manifest, out / "build-manifest.json")


if __name__ == "__main__":
    main()
