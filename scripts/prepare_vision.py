"""Prepare checksum-locked CPU vision packs for reproducible onefile variants.

Downloads run only during explicit developer preparation, never at app startup.
CUDA runners can be supplied separately; the pinned portable preset uses CPU.
"""
import argparse
import json
import os
import platform
import shutil
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

from ocready.core.models import ModelPack
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


def prepare_pack(preset: dict, runner: Path, folder: Path, cuda_runner: Path | None = None) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    for record in preset["files"]:
        fetch(record, folder / record["file"])
    model, projector = [folder / record["file"] for record in preset["files"][:2]]
    pack = ModelPack(preset["id"], preset["name"], str(runner.resolve()), str(model.resolve()),
                     str(projector.resolve()), cuda_runner=str(cuda_runner.resolve()) if cuda_runner else "",
                     memory_mb=preset["memory_mb"], tokens=preset["tokens"], prompt=preset["prompt"],
                     languages=preset["languages"], source=f"https://huggingface.co/{preset['repo']}",
                     license=preset["license"])
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
        + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preset", action="append", choices=("smol", "glm"), required=True,
                        help="Repeat to prepare multiple choices; GLM requires Studio.")
    parser.add_argument("--runtime-dir", type=Path, default=ROOT / "runtime/vision-cpu")
    parser.add_argument("--model-dir", type=Path, default=ROOT / "models/vision")
    parser.add_argument("--cuda-runner", type=Path, help="Optional separately provisioned compatible CUDA runner")
    args = parser.parse_args()
    lock = json.loads((ROOT / "assets/vision-lock.json").read_text(encoding="utf-8"))
    runner = prepare_runner(lock["runner"], args.runtime_dir.resolve())
    for name in dict.fromkeys(args.preset):
        print(prepare_pack(lock["packs"][name], runner, args.model_dir.resolve() / name, args.cuda_runner))


if __name__ == "__main__":
    main()
