"""Build a pinned CUDA llama.cpp runner without changing the installed GPU driver.

This optional developer tool downloads NVIDIA's checksum-pinned redistributable
components into runtime/cuda-12.4 and builds only the multimodal CLI. Nothing is
installed system-wide. Install the cuda-build extra before running this script.
"""
import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime"
CUDA_BASE = "https://developer.download.nvidia.com/compute/cuda/redist/"
LLAMA_COMMIT = "940a30ee3b5593e1a66fe0aadc3b731989022552"
COMPONENTS = {
    "cuda_nvcc": ("cuda_nvcc/linux-x86_64/cuda_nvcc-linux-x86_64-12.4.131-archive.tar.xz", "7ffba1ada0e4b8c17e451ac7a60d386aa2642ecd08d71202a0b100c98bd74681"),
    "cuda_cudart": ("cuda_cudart/linux-x86_64/cuda_cudart-linux-x86_64-12.4.127-archive.tar.xz", "0483bff9a36e7a44465db3cd42874f6f70f019297dcf803fbefcbf58d7448c8f"),
    "cuda_cccl": ("cuda_cccl/linux-x86_64/cuda_cccl-linux-x86_64-12.4.127-archive.tar.xz", "e1636f27a142d24e73dfd831c54bbf5575b498fd5900648d7372fae46f824fdf"),
    "libcublas": ("libcublas/linux-x86_64/libcublas-linux-x86_64-12.4.5.8-archive.tar.xz", "c267c4d2cd42065ae2c30ca41a43ddce4e0ecc5484de23f299e3c397b5506eda"),
}


def digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch(url: str, target: Path, expected: str | None = None) -> None:
    if target.is_file() and (not expected or digest_file(target) == expected):
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(".partial")
    print(f"Downloading {target.name}…", flush=True)
    with urllib.request.urlopen(url, timeout=120) as response, partial.open("wb") as output:
        shutil.copyfileobj(response, output, 1024 * 1024)
    if expected and digest_file(partial) != expected:
        partial.unlink()
        raise RuntimeError(f"Checksum mismatch for {target.name}")
    partial.replace(target)


def component(record: tuple[str, tuple[str, str]]) -> Path:
    name, (relative, expected) = record
    archive_path = RUNTIME / "cuda-downloads" / Path(relative).name
    fetch(CUDA_BASE + relative, archive_path, expected)
    extracted = RUNTIME / "cuda-components" / name
    if not (extracted / ".ready").exists():
        extracted.mkdir(parents=True, exist_ok=True)
        with tarfile.open(archive_path) as archive:
            members = [m for m in archive.getmembers() if name != "libcublas" or not m.name.endswith(".a")]
            archive.extractall(extracted, members=members, filter="data")
        (extracted / ".ready").touch()
    return next(p for p in extracted.iterdir() if p.is_dir())


def merge_component(source: Path, target: Path) -> None:
    for path in sorted(source.rglob("*")):
        destination = target / path.relative_to(source)
        if path.is_symlink():
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.unlink(missing_ok=True)
            destination.symlink_to(path.readlink())
        elif path.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
        elif path.is_file():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--architecture", default="75", help="Native CUDA compute capability, e.g. 75 for GTX 1660 Ti")
    parser.add_argument("--host-cxx", type=Path, help="Optional compatible host compiler, e.g. g++-12")
    parser.add_argument("--jobs", type=int, default=3)
    args = parser.parse_args()
    if sys.platform != "linux":
        parser.error("This optional tool currently provisions Linux x86_64. Windows can use upstream CUDA runners.")
    if not args.architecture.isdigit():
        parser.error("architecture must be numeric, e.g. 75")
    environment = os.environ.copy()
    environment["PATH"] = str(Path(sys.executable).parent) + os.pathsep + environment.get("PATH", "")
    if not shutil.which("cmake", path=environment["PATH"]):
        parser.error("Install the cuda-build extra first: uv sync --extra dev --extra cuda-build")
    toolkit = RUNTIME / "cuda-12.4"
    toolkit.mkdir(parents=True, exist_ok=True)
    signature = hashlib.sha256(json.dumps({"components": COMPONENTS, "libc": platform.libc_ver()}, sort_keys=True).encode()).hexdigest()
    marker = toolkit / ".ocready-sdk"
    ready = marker.is_file() and marker.read_text() == signature
    if ready:
        directories = []
    else:
        with ThreadPoolExecutor(max_workers=4) as executor:
            directories = list(executor.map(component, COMPONENTS.items()))
    for directory in directories:
        merge_component(directory, toolkit)
        for license_file in directory.glob("*LICENSE*"):
            notices = toolkit / "notices"
            notices.mkdir(exist_ok=True)
            shutil.copy2(license_file, notices / f"{directory.name}-{license_file.name}")
    if not (toolkit / "lib64").exists() and (toolkit / "lib").exists():
        (toolkit / "lib64").symlink_to("lib", target_is_directory=True)
    # CUDA 12.4 declarations predate glibc 2.41's C23 pi-math functions.
    # Apply the local SDK compatibility correction documented by llama.cpp:
    # https://github.com/ggml-org/llama.cpp/blob/master/docs/build.md
    # This changes only our extracted toolchain, never system headers or drivers.
    libc_name, libc_version = platform.libc_ver()
    if libc_name == "glibc" and tuple(int(v) for v in libc_version.split(".")[:2]) >= (2, 41):
        header = toolkit / "include" / "crt" / "math_functions.h"
        content = header.read_text()
        patched = re.sub(r"(extern[^\n]*\b(?:sinpi|cospi|sinpif|cospif)\((?:float|double) x\))\s*;",
                         r"\1 noexcept (true);", content)
        if content != patched:
            header.write_text(patched)
    marker.write_text(signature)
    environment["LD_LIBRARY_PATH"] = str(toolkit / "lib64") + os.pathsep + environment.get("LD_LIBRARY_PATH", "")
    subprocess.run([str(toolkit / "bin" / "nvcc"), "--version"], check=True)
    source_tar = RUNTIME / "cuda-downloads" / f"llama-{LLAMA_COMMIT}.tar.gz"
    fetch(f"https://github.com/ggml-org/llama.cpp/archive/{LLAMA_COMMIT}.tar.gz", source_tar)
    source = RUNTIME / f"llama.cpp-{LLAMA_COMMIT}"
    if not source.exists():
        with tarfile.open(source_tar) as archive:
            archive.extractall(RUNTIME, filter="data")
    build = RUNTIME / "llama-cuda-native"
    configure = ["cmake", "-S", str(source), "-B", str(build), "-G", "Ninja",
                 "-DCMAKE_BUILD_TYPE=Release", "-DGGML_CUDA=ON", "-DLLAMA_CURL=OFF",
                 "-DLLAMA_BUILD_TESTS=OFF", "-DLLAMA_BUILD_EXAMPLES=OFF", "-DLLAMA_BUILD_TOOLS=ON",
                 "-DGGML_NATIVE=OFF", "-DCMAKE_CUDA_ARCHITECTURES=" + args.architecture + "-real",
                 "-DCUDAToolkit_ROOT=" + str(toolkit), "-DCMAKE_CUDA_COMPILER=" + str(toolkit / "bin" / "nvcc")]
    if args.host_cxx:
        cxx = args.host_cxx.resolve()
        cc = cxx.with_name(cxx.name.replace("g++", "gcc"))
        if cxx.is_relative_to(RUNTIME):
            # Debian dev packages use relative links into /usr/lib. When extracted
            # locally, reconnect those aliases to the installed ABI-compatible runtimes.
            for link in cxx.parent.parent.glob("lib/gcc/*/*/*.so"):
                if not link.is_symlink() or link.exists():
                    continue
                candidate = Path("/usr/lib/x86_64-linux-gnu") / link.readlink().name
                if candidate.is_file():
                    link.unlink()
                    link.symlink_to(candidate)
        configure += ["-DCMAKE_CUDA_HOST_COMPILER=" + str(cxx), "-DCMAKE_CXX_COMPILER=" + str(cxx),
                      "-DCMAKE_C_COMPILER=" + str(cc), "-UOpenMP_*"]
    subprocess.run(configure, env=environment, check=True)
    subprocess.run(["cmake", "--build", str(build), "--target", "llama-mtmd-cli", "-j", str(args.jobs)],
                   env=environment, check=True)
    output = build / "bin"
    for library in (toolkit / "lib64").glob("*.so*"):
        if library.is_file():
            target = output / library.name
            if library.is_symlink():
                target.unlink(missing_ok=True)
                target.symlink_to(library.readlink().name)
            else:
                shutil.copy2(library, target)
    shutil.copy2(source / "LICENSE", output / "LICENSE.llama.cpp")
    if (toolkit / "notices").is_dir():
        shutil.copytree(toolkit / "notices", output / "notices", dirs_exist_ok=True)
    (output / "build-manifest.json").write_text(json.dumps({"llama_commit": LLAMA_COMMIT,
        "cuda_components": COMPONENTS, "architecture": args.architecture, "driver_modified": False}, indent=2))
    print(f"Built local CUDA runner: {output / 'llama-mtmd-cli'}", flush=True)


if __name__ == "__main__":
    main()
