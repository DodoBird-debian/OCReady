"""Fetch pinned official PP-OCRv5 assets and write a local worker manifest."""
import argparse
import json
import os
import tempfile
import urllib.request
from pathlib import Path

from ocready.core.neural_packs import NeuralPack
from scripts.provenance import file_sha256

ROOT = Path(__file__).resolve().parents[1]


def fetch(url: str, path: Path, expected: str) -> None:
    if path.is_file() and file_sha256(path) == expected:
        return
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".neural-download-", delete=False) as stream:
            temporary = Path(stream.name)
            with urllib.request.urlopen(url, timeout=60) as response:
                while chunk := response.read(1024 * 1024):
                    stream.write(chunk)
        if file_sha256(temporary) != expected:
            raise RuntimeError(f"The checksum did not match for {path.name}.")
        temporary.replace(path)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    default_runner = ROOT / "runtime/neural-runner/cpu/neural_runner.dist" / ("ocready-neural-runner.exe" if os.name == "nt" else "ocready-neural-runner")
    parser.add_argument("--runner", type=Path, default=default_runner)
    parser.add_argument("--cuda-runner", type=Path)
    parser.add_argument("--model-dir", type=Path, default=ROOT / "models/ppocr-v5")
    args = parser.parse_args()
    if not args.runner.is_file():
        parser.error("Compile the worker first: python -m scripts.build_neural_runner")
    import yaml
    lock = json.loads((ROOT / "assets/neural-lock.json").read_text(encoding="utf-8"))
    folder = args.model_dir.resolve()
    folder.mkdir(parents=True, exist_ok=True)
    for item in lock["files"]:
        url = item.get("url") or f"https://huggingface.co/{item['repo']}/resolve/{item['revision']}/{item['remote']}"
        fetch(url, folder / item["file"], item["sha256"])
    config = yaml.safe_load((folder / "rec-inference.yml").read_text(encoding="utf-8"))
    dictionary = folder / "arabic-keys.txt"
    dictionary.write_text("\n".join(config["PostProcess"]["character_dict"]) + "\n", encoding="utf-8", newline="\n")
    if file_sha256(dictionary) != lock["derived_dictionary_sha256"]:
        raise RuntimeError("The derived character dictionary differs from its locked reference.")
    pack = NeuralPack("ppocr-v5-arabic", "Neural OCR · Arabic + English", str(args.runner.resolve()),
                      str(folder / "det-inference.onnx"), str(folder / "rec-inference.onnx"), str(dictionary),
                      cuda_runner=str(args.cuda_runner.resolve()) if args.cuda_runner else "", memory_mb=600 if args.cuda_runner else 300,
                      source="https://huggingface.co/PaddlePaddle/arabic_PP-OCRv5_mobile_rec_onnx", license="Apache-2.0")
    pack.validate()
    (folder / "pack.json").write_text(json.dumps(pack.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    sources = [f"{item['repo']} @ {item['revision']} / {item['remote']}" for item in lock["files"] if "repo" in item]
    (folder / "NOTICE.txt").write_text("Official PaddlePaddle PP-OCRv5 assets, Apache-2.0.\n" + "\n".join(sources)
                                      + "\nDictionary derived from PostProcess.character_dict in the locked recognition configuration.\n", encoding="utf-8")
    print(folder / "pack.json")


if __name__ == "__main__":
    main()
