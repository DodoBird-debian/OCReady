"""Standalone JSON v1 reference worker backed by a bundled llama.cpp CLI.

This process has no GUI or numerical Python dependencies. The parent application
owns containment and cancellation for this worker and its native descendants.
"""
import argparse
import json
import os
import re
import struct
import subprocess
import sys
from pathlib import Path

from ocready.core.backend_errors import cuda_failure_detail


def runner_path() -> Path:
    return Path(__file__).resolve().parent / "llama" / ("llama-mtmd-cli.exe" if os.name == "nt" else "llama-mtmd-cli")


def environment(runner: Path) -> dict[str, str]:
    env = os.environ.copy()
    if os.name == "nt":
        env["PATH"] = str(runner.parent) + os.pathsep + env.get("PATH", "")
    else:
        env["LD_LIBRARY_PATH"] = str(runner.parent) + os.pathsep + str(runner.parent.parent / "lib")
    return env


def image_size(path: Path) -> tuple[int, int]:
    with path.open("rb") as stream:
        header = stream.read(24)
    if len(header) != 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise ValueError("The reference worker expects the application's processed PNG input.")
    width, height = struct.unpack(">II", header[16:24])
    if not width or not height:
        raise ValueError("The PNG dimensions are invalid.")
    return width, height


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ocready-vision-capabilities", action="store_true")
    parser.add_argument("--ocready-vision-v1", action="store_true")
    parser.add_argument("--image", type=Path)
    parser.add_argument("--model", type=Path)
    parser.add_argument("--projector", type=Path)
    parser.add_argument("--prompt")
    parser.add_argument("--max-output-tokens", type=int, default=512)
    parser.add_argument("--max-image-tokens", type=int, default=1024)
    parser.add_argument("--backend", choices=("cpu", "cuda"), default="cpu")
    args = parser.parse_args(argv)
    runner = runner_path()
    try:
        if not runner.is_file():
            raise ValueError("The reference worker's bundled llama-mtmd-cli is missing.")
        if args.ocready_vision_capabilities:
            probe = subprocess.run([str(runner), "--list-devices"], capture_output=True, timeout=20,
                                   env=environment(runner))
            devices = (probe.stdout + probe.stderr).decode("utf-8", errors="replace")
            backends = ["cpu"]
            if probe.returncode == 0 and re.search(r"CUDA\d|CUDA\s*:", devices, re.IGNORECASE):
                backends.append("cuda")
            print(json.dumps({"schema": 1, "backends": backends}))
            return 0
        if not args.ocready_vision_v1 or not all((args.image, args.model, args.projector, args.prompt)):
            raise ValueError("Supply a PNG image, GGUF model, matching projector and prompt for JSON v1 recognition.")
        if not 64 <= args.max_output_tokens <= 2048 or not 1 <= args.max_image_tokens <= 1024:
            raise ValueError("Output/image token limits are outside the reference worker's supported range.")
        width, height = image_size(args.image)
        command = [str(runner), "-m", str(args.model), "--mmproj", str(args.projector), "--image", str(args.image),
                   "-p", args.prompt, "-n", str(args.max_output_tokens), "--temp", "0", "--seed", "1", "-c", "4096",
                   "-b", "256", "-ub", "128", "-t", str(min(8, os.cpu_count() or 2)),
                   "--image-max-tokens", str(args.max_image_tokens), "--no-warmup", "--log-colors", "off",
                   "-ngl", "99" if args.backend == "cuda" else "0"]
        if args.backend == "cpu":
            command.append("--no-mmproj-offload")
        result = subprocess.run(command, capture_output=True, timeout=300, env=environment(runner))
        if result.returncode:
            error = result.stderr.decode("utf-8", errors="replace")
            tail = error[-16_000:]
            sys.stderr.write(tail)
            gpu_detail = cuda_failure_detail(error)
            if gpu_detail and gpu_detail not in tail:
                sys.stderr.write("\n" + gpu_detail + "\n")
            status = str(result.returncode)
            if os.name == "nt":
                status += f" (0x{result.returncode & 0xFFFFFFFF:08X})"
            sys.stderr.write(f"\nNative vision runner exited with code {status}.\n")
            return 2
        text = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", result.stdout.decode("utf-8", errors="strict")).strip()
        for token in ("<|im_end|>", "<|endoftext|>", "<|eot_id|>"):
            text = text.removesuffix(token).rstrip()
        print(json.dumps({"schema": 1, "width": width, "height": height, "text": text,
                          "backend": args.backend.upper()}, ensure_ascii=True))
        return 0
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print(f"Local vision worker failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
