"""Build a curated neural, combined, or multimodal single-file variant.

Prepare the classical runtime and standalone neural worker/pack first. Vision
weights are checksum-provisioned here only for an explicit multimodal build.
"""
import argparse
import subprocess
import sys

from scripts.prepare_vision import ROOT


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--edition", choices=("everyday", "studio"), required=True)
    parser.add_argument("--variant", choices=("neural", "combined", "multimodal"), required=True)
    parser.add_argument("--jobs", type=int, default=2)
    args = parser.parse_args()
    methods = "neural" if args.variant == "neural" else "fast,best,vision,neural"
    command = [sys.executable, "-m", "scripts.build", "--edition", args.edition, "--methods", methods,
               "--neural-pack", str(ROOT / "models/ppocr-v5/pack.json"), "--variant", args.variant, "--jobs", str(args.jobs)]
    if args.variant == "multimodal":
        presets = ["smol"] + (["glm"] if args.edition == "studio" else [])
        prepare = [sys.executable, "-m", "scripts.prepare_vision"]
        for preset in presets:
            prepare += ["--preset", preset]
            command += ["--model-pack", str(ROOT / "models/vision" / preset / "pack.json")]
        subprocess.run(prepare, cwd=ROOT, check=True)
    subprocess.run(command, cwd=ROOT, check=True)


if __name__ == "__main__":
    main()
