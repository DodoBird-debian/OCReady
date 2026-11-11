"""Prepare checksum-locked CPU vision packs for reproducible onefile variants.

Downloads run only during explicit developer preparation, never at app startup.
CUDA runners can be supplied separately; the pinned portable preset uses CPU.
"""
import argparse
import json
import os
import platform
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

from ocready.core.models import ModelPack
from ocready.engines.vision_adapters import local_environment
from scripts.provenance import file_sha256

ROOT = Path(__file__).resolve().parents[1]


def fetch(record: dict, target: Path) -> None:
    """Publish only an exact-size, exact-digest file; retain valid cached files."""
    expected_size = record["bytes"]
    if target.is_file() and target.stat().st_size == expected_size and file_sha256(target) == record["sha256"]:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".vision-download-", delete=False) as output:
            temporary = Path(output.name)
            print(f"Downloading {target.name}…", flush=True)
            received = 0
            with urllib.request.urlopen(record["url"], timeout=120) as response:
                while chunk := response.read(1024 * 1024):
                    received += len(chunk)
                    if received > expected_size:
                        raise RuntimeError(f"Download exceeds the locked size: {target.name}")
                    output.write(chunk)
        if received != expected_size or file_sha256(temporary) != record["sha256"]:
            raise RuntimeError(f"Download differs from its locked reference: {target.name}")
        temporary.replace(target)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)


def archive_path(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or "\\" in name or ":" in name:
        raise ValueError(f"Unsafe runtime archive path: {name}")
    return path


def extract_runner(archive_file: Path, destination: Path) -> Path:
    """Extract a locked upstream CPU archive, rejecting escaping links and paths."""
    if archive_file.suffix == ".zip":
        with zipfile.ZipFile(archive_file) as archive:
            members = archive.infolist()
            if len(members) > 5000 or sum(item.file_size for item in members) > 500_000_000:
                raise ValueError("The CPU runtime archive is too large.")
            for item in members:
                archive_path(item.filename)
                if (item.external_attr >> 16) & 0o170000 == 0o120000:
                    raise ValueError("Links are not supported in the Windows CPU archive.")
            archive.extractall(destination)
    else:
        with tarfile.open(archive_file) as archive:
            members = archive.getmembers()
            if len(members) > 5000 or sum(item.size for item in members) > 500_000_000:
                raise ValueError("The CPU runtime archive is too large.")
            for item in members:
                path = archive_path(item.name)
                if item.issym() or item.islnk():
                    link = archive_path(item.linkname)
                    target = (path.parent / link) if item.issym() else link
                    archive_path(str(target))
                elif not (item.isfile() or item.isdir()):
                    raise ValueError("Unsupported CPU runtime archive entry.")
            archive.extractall(destination, filter="data")
    runners = [path for name in ("llama-mtmd-cli", "llama-mtmd-cli.exe") for path in destination.rglob(name) if path.is_file()]
    if len(runners) != 1:
        raise ValueError("The CPU archive must contain exactly one multimodal runner.")
    return runners[0]


def prepare_runner(lock: dict, runtime: Path) -> Path:
    machine = platform.machine().lower()
    if machine not in {"x86_64", "amd64"} or platform.system() not in {"Linux", "Windows"}:
        raise RuntimeError("The pinned CPU runtime currently supports Linux/Windows x86_64.")
    platform_key = platform.system().lower() + "-x86_64"
    record = lock["platforms"][platform_key]
    archive_file = runtime / "downloads" / record["file"]
    fetch(record, archive_file)
    destination = runtime / f"{lock['release']}-{platform_key}"
    # Re-extract from the verified archive rather than trusting a stale marker.
    with tempfile.TemporaryDirectory(dir=runtime, prefix=".vision-extract-") as temporary:
        staging = Path(temporary)
        runner = extract_runner(archive_file, staging)
        relative = runner.relative_to(staging)
        fetch(lock["license"], runner.parent / "LICENSE-llama.txt")
        (runner.parent / "NOTICE-ocready.txt").write_text(
            f"llama.cpp {lock['release']} @ {lock['source_revision']}\n"
            f"CPU release archive SHA256: {record['sha256']}\n"
            "Source and third-party notices: https://github.com/ggml-org/llama.cpp/tree/"
            + lock["source_revision"] + "\n", encoding="utf-8")
        if destination.exists():
            shutil.rmtree(destination)
        shutil.move(str(staging), destination)
    return destination / relative


def quantize_model(derived: dict, folder: Path, quantizer: Path | None) -> Path:
    output = folder / derived["file"]
    if output.is_file() and output.stat().st_size == derived["bytes"] and file_sha256(output) == derived["sha256"]:
        return output
    if not quantizer or not quantizer.is_file():
        raise RuntimeError("This preset needs the pinned CPU release's llama-quantize tool; supply --quantizer if using another worker.")
    with tempfile.TemporaryDirectory(dir=folder, prefix=".vision-quantize-") as temporary:
        staged = Path(temporary) / output.name
        subprocess.run([str(quantizer), "--allow-requantize", str(folder / derived["input"]), str(staged), derived["quantization"]],
                       env=local_environment(str(quantizer)), check=True, timeout=300)
        actual_size = staged.stat().st_size if staged.is_file() else 0
        actual_hash = file_sha256(staged) if staged.is_file() else "missing"
        if actual_size != derived["bytes"] or actual_hash != derived["sha256"]:
            raise RuntimeError(f"Derived vision weights differ from the locked output: {actual_size} bytes, SHA256 {actual_hash}; no model was published.")
        staged.replace(output)
    return output


def prepare_pack(preset: dict, runner: Path, folder: Path, cuda_runner: Path | None = None,
                 adapter: str = "llama.cpp", quantizer: Path | None = None) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    for record in preset["files"]:
        fetch(record, folder / record["file"])
    model, projector = [folder / record["file"] for record in preset["files"][:2]]
    if preset.get("derived_model"):
        model = quantize_model(preset["derived_model"], folder, quantizer)
    pack = ModelPack(preset["id"], preset["name"], str(runner.resolve()), str(model.resolve()),
                     str(projector.resolve()), cuda_runner=str(cuda_runner.resolve()) if cuda_runner else "",
                     memory_mb=preset["memory_mb"], tokens=preset["tokens"], prompt=preset["prompt"],
                     languages=preset["languages"], source=f"https://huggingface.co/{preset['repo']}",
                     license=preset["license"], adapter=adapter)
    pack.validate()
    record = pack.to_dict()
    for key in ("runner", "model", "projector", "cuda_runner"):
        if record[key]:
            record[key] = Path(os.path.relpath(record[key], folder)).as_posix()
    manifest = folder / "pack.json"
    manifest.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (folder / "NOTICE-ocready.txt").write_text(
        f"Model: {preset['repo']} @ {preset['revision']}\nLicense: {preset['license']}\n"
        f"{preset['limitations']}\n\n"
        + "\n".join(f"{item['file']}: SHA256 {item['sha256']}\n{item['url']}" for item in preset["files"])
        + ("\nDerived model: " + json.dumps(preset["derived_model"], sort_keys=True) if preset.get("derived_model") else "")
        + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preset", action="append", choices=("smol", "smol-q4", "glm", "qwen3"), required=True,
                        help="Repeat to prepare multiple choices; GLM and Qwen3 require Studio.")
    parser.add_argument("--runtime-dir", type=Path, default=ROOT / "runtime/vision-cpu")
    parser.add_argument("--model-dir", type=Path, default=ROOT / "models/vision")
    parser.add_argument("--cuda-runner", type=Path, help="Optional separately provisioned compatible CUDA runner")
    parser.add_argument("--runner", type=Path, help="Use an existing compatible CPU worker instead of provisioning the CPU CLI")
    parser.add_argument("--adapter", choices=("llama.cpp", "json-cli-v1"), default="llama.cpp")
    parser.add_argument("--quantizer", type=Path, help="Optional explicit llama-quantize for derived compact presets")
    args = parser.parse_args()
    lock = json.loads((ROOT / "assets/vision-lock.json").read_text(encoding="utf-8"))
    if args.adapter != "llama.cpp" and not args.runner:
        parser.error("Supply --runner for the selected adapter; see scripts.build_vision_bridge.")
    runner = args.runner.resolve() if args.runner else prepare_runner(lock["runner"], args.runtime_dir.resolve())
    quantizer = args.quantizer.resolve() if args.quantizer else runner.with_name("llama-quantize.exe" if os.name == "nt" else "llama-quantize")
    for name in dict.fromkeys(args.preset):
        print(prepare_pack(lock["packs"][name], runner, args.model_dir.resolve() / name, args.cuda_runner, args.adapter, quantizer))


if __name__ == "__main__":
    main()
