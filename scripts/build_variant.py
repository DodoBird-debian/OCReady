"""Build a curated neural, combined, or multimodal single-file variant.

Prepare the classical runtime and standalone neural worker/pack first. Vision
weights are checksum-provisioned here only for an explicit multimodal build.
"""
import argparse
import dataclasses
import json
import os
import subprocess
import sys
from pathlib import Path

from ocready.core.models import load_pack
from scripts.prepare_vision import ROOT
from scripts.qt_runtime import require_x11
from scripts.variants import MODEL_VARIANTS, vision_presets


def json_pack_manifest(native_manifest: Path, worker: Path) -> Path:
    native = load_pack(native_manifest)
    pack = dataclasses.replace(native, id=native.id + "-json",
                               runner=str(worker.resolve()), cuda_runner="", adapter="json-cli-v1")
    pack.validate()
    manifest = native_manifest.with_name("pack-json.json")
    manifest.write_text(json.dumps(pack.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--edition", choices=("everyday", "studio"), required=True)
    parser.add_argument("--variant", choices=MODEL_VARIANTS, required=True)
    parser.add_argument("--jobs", type=int, default=2)
    args = parser.parse_args()
    require_x11(output=ROOT / "dist" / f"{args.edition}-{args.variant}" / "qt-source-runtime.json")
    methods = "neural" if args.variant == "neural" else "neural,fast,best,vision"
    command = [sys.executable, "-m", "scripts.build", "--edition", args.edition, "--methods", methods,
               "--neural-pack", str(ROOT / "models/ppocr-v5/pack.json"), "--variant", args.variant, "--jobs", str(args.jobs)]
    presets = vision_presets(args.edition, args.variant)
    if presets:
        prepare = [sys.executable, "-m", "scripts.prepare_vision"]
        for preset in presets:
            prepare += ["--preset", preset]
        subprocess.run(prepare, cwd=ROOT, check=True)
        manifests = [ROOT / "models/vision" / preset / "pack.json" for preset in presets]
        if args.variant == "multimodal-json":
            native = load_pack(manifests[0])
            subprocess.run([sys.executable, "-m", "scripts.build_vision_bridge", "--runner", native.runner,
                            "--jobs", str(args.jobs)], cwd=ROOT, check=True)
            worker = ROOT / "runtime/vision-bridge/cpu/vision_bridge.dist" / ("ocready-vision-bridge.exe" if os.name == "nt" else "ocready-vision-bridge")
            manifests = [json_pack_manifest(manifest, worker) for manifest in manifests]
        for manifest in manifests:
            command += ["--model-pack", str(manifest)]
    subprocess.run(command, cwd=ROOT, check=True)


if __name__ == "__main__":
    main()
