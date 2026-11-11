"""Measure supported onefile caching in an isolated, disposable native probe.

This does not enable caching in OCReady or store document content. It compares
the same incompressible packaged asset, checks repair, and stresses cold races.
"""
import argparse
import concurrent.futures
import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from scripts.payload_memory import compiler_overlay, overlay_environment
from scripts.provenance import file_sha256, require_unchanged, source_record

ROOT = Path(__file__).resolve().parents[1]


def launch(binary: Path, expected: str) -> dict:
    started = time.perf_counter()
    try:
        result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=120)
        try:
            value = json.loads(result.stdout)
        except ValueError:
            value = {}
        return {"elapsed_seconds": time.perf_counter() - started, "exit_code": result.returncode,
                "payload_matches": result.returncode == 0 and value.get("sha256") == expected,
                "error": result.stderr[-4000:] if result.returncode else ""}
    except subprocess.TimeoutExpired:
        return {"elapsed_seconds": time.perf_counter() - started, "exit_code": None,
                "payload_matches": False, "error": "Probe exceeded 120 seconds."}


def probe(output: Path, size_mib: int, rounds: int, jobs: int) -> dict:
    source = source_record(ROOT)
    output.parent.mkdir(parents=True, exist_ok=True)
    report = {"source": source, "platform": platform.platform(), "python": platform.python_version(),
              "nuitka": importlib.metadata.version("Nuitka"), "payload_bytes": size_mib * 1024 * 1024,
              "scope": "Synthetic developer probe only; not OCReady startup, memory or platform certification.",
              "cache_policy": "Supported cached mode with archive payload; default comparison uses temporary streaming mode."}
    with tempfile.TemporaryDirectory(prefix="startup-probe-", dir=output.parent) as temporary:
        work = Path(temporary).resolve()
        asset = work / "payload.bin"
        with asset.open("wb") as stream:
            for _ in range(size_mib):
                stream.write(os.urandom(1024 * 1024))
        expected = file_sha256(asset)
        program = work / "probe.py"
        program.write_text(
            "import hashlib, json\nfrom pathlib import Path\n"
            "digest = hashlib.sha256()\n"
            "with Path(__file__).with_name('payload.bin').open('rb') as stream:\n"
            "    while block := stream.read(1024 * 1024): digest.update(block)\n"
            "print(json.dumps({'sha256': digest.hexdigest()}))\n", encoding="utf-8")
        cache = work / "cache"
        binaries = {}
        with compiler_overlay(work) as (overlay, trim):
            report["payload_memory"] = trim
            for mode in ("temporary", "cached"):
                folder = work / mode
                command = [sys.executable, "-m", "nuitka", str(program), "--mode=onefile", "--low-memory", "--lto=no",
                           f"--jobs={jobs}", f"--output-dir={folder}", "--output-filename=probe",
                           f"--include-data-files={asset}=payload.bin", "--assume-yes-for-downloads"]
                if mode == "cached":
                    command += ["--onefile-cache-mode=cached", "--onefile-as-archive", f"--onefile-tempdir-spec={cache}"]
                print(f"Compiling {mode} startup probe…", flush=True)
                subprocess.run(command, cwd=work, env=overlay_environment(os.environ.copy(), overlay), check=True, timeout=600)
                binaries[mode] = folder / ("probe.exe" if os.name == "nt" else "probe")
        require_unchanged(ROOT, source)
        report["asset_sha256"] = expected
        report["binaries"] = {mode: {"sha256": file_sha256(binary), "bytes": binary.stat().st_size}
                              for mode, binary in binaries.items()}
        report["temporary_runs"] = [launch(binaries["temporary"], expected) for _ in range(rounds)]
        report["cached_cold"] = launch(binaries["cached"], expected)
        report["cached_warm_runs"] = [launch(binaries["cached"], expected) for _ in range(rounds)]
        cached_asset = cache / "payload.bin"
        if cached_asset.is_file():
            with cached_asset.open("r+b") as stream:
                stream.seek(cached_asset.stat().st_size // 2)
                value = stream.read(1)
                stream.seek(-1, 1)
                stream.write(bytes([value[0] ^ 0xFF]))
            report["cached_repair"] = launch(binaries["cached"], expected)
        else:
            report["cached_repair"] = {"payload_matches": False, "error": "The initial cache was not created."}
        races = []
        for _ in range(rounds):
            shutil.rmtree(cache, ignore_errors=True)
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(launch, binaries["cached"], expected) for _ in range(2)]
                races.append([future.result() for future in futures])
        report["concurrent_cold_pairs"] = races
    report["sources_changed_during_run"] = source_record(ROOT) != source
    sequential = [*report["temporary_runs"], report["cached_cold"], *report["cached_warm_runs"], report["cached_repair"]]
    report["sequential_payloads_valid"] = all(row["payload_matches"] for row in sequential)
    report["concurrent_failures"] = sum(not row["payload_matches"] for pair in report["concurrent_cold_pairs"] for row in pair)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "test-output/startup-probe.json")
    parser.add_argument("--size-mib", type=int, default=128)
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--jobs", type=int, default=2)
    args = parser.parse_args()
    if not 8 <= args.size_mib <= 1024 or not 1 <= args.rounds <= 10 or not 1 <= args.jobs <= 16:
        parser.error("Use 8–1024 MiB, 1–10 rounds and 1–16 compiler jobs.")
    report = probe(args.output.resolve(), args.size_mib, args.rounds, args.jobs)
    print(f"Startup measurements saved in {args.output}; cache safety is not assumed.")
    if report["sources_changed_during_run"]:
        parser.exit(2, "Sources changed during the probe; do not treat it as clean evidence.\n")
    if not report["sequential_payloads_valid"]:
        parser.exit(2, "A sequential payload or repair check failed; inspect the saved report.\n")


if __name__ == "__main__":
    main()
