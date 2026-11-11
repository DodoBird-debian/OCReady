"""Measure fresh-process OCR workflows, including the GUI and child processes.

Samples RSS every 10 ms. This is reproducible workload evidence, not a proof of
an absolute OS-enforced ceiling. Reports include the observed peak and budget.
"""
import argparse
import json
import math
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import psutil
from PIL import Image, ImageOps

from ocready.core.editions import EDITIONS
from ocready.core.memory import tree_rss
from ocready.core.timeouts import gui_workload_timeout_seconds, observed_workload_timeout_seconds
from scripts.packaged_environment import execution_policy, gui_test_platform, runtime_test_environment
from scripts.provenance import file_sha256, source_record

ROOT = Path(__file__).resolve().parents[1]


def redact_details(record: dict) -> dict:
    """Remove document contents without hiding a failed GUI admission check."""
    details = record.get("result", record)
    safe = {key: details[key] for key in ("elapsed", "peak_rss", "engine", "backend", "containment",
                                          "worker_limit", "worker_peak", "error", "rss") if key in details}
    words = details.get("words", [])
    safe["words"] = len(words) if isinstance(words, list) else words
    if record.get("error"):
        safe["error"] = record["error"]
    for key in ("qt_platform", "clipboard_copy_verified", "source_selection_verified", "deadline_seconds", "input_route"):
        if key in record:
            safe[key] = record[key]
    return safe


def check_requested_engine(result: dict, method: str | None, pack_id: str | None) -> None:
    if not method or result["exit_code"]:
        return
    engine = result["details"].get("engine", "")
    expected = f"{method}:{pack_id}" if pack_id else method
    matched = engine == expected or (not pack_id and method in {"vision", "neural"} and engine.startswith(method + ":"))
    if not matched:
        result["exit_code"] = 2
        result["details"]["error"] = f"Requested {expected}, but the workload returned {engine or 'no engine identity'}."


def make_image(path: Path, edition: str, dark=False, maximum=False) -> None:
    sample = Image.open(ROOT / "assets" / "sample-bilingual.png").convert("RGB")
    if maximum:
        cap = EDITIONS[edition].max_pixels
        width = int(math.sqrt(cap * 1.4))
        height = cap // width
        image = Image.new("RGB", (width, height), "white")
        # Tile realistic bilingual text instead of benchmarking an almost blank page.
        for y in range(0, height, sample.height):
            for x in range(0, width, sample.width):
                image.paste(sample, (x, y))
    else:
        image = sample
    if dark:
        image = ImageOps.invert(image)
    image.save(path)


def gui_child(image_path: str, edition: str, output: str, loops: int, pack_path: Path | None = None,
              neural_path: Path | None = None) -> int:
    from PySide6.QtCore import QTimer
    from PySide6.QtGui import QImage
    from PySide6.QtWidgets import QApplication

    from ocready.ui.theme import apply_theme
    from ocready.ui.window import MainWindow
    app = QApplication.instance() or QApplication([])
    apply_theme(app)
    window = MainWindow(edition=edition)
    if pack_path:
        from ocready.core.models import load_pack
        pack = load_pack(pack_path)
        window.packs = [pack]
        window.refresh_methods()
    if neural_path:
        from ocready.core.neural_packs import load_neural_pack
        neural_pack = load_neural_pack(neural_path)
        window.neural_packs = [neural_pack]
        window.refresh_methods()
    window.show()
    remaining = loops
    measurements = []
    failed = False

    def run_next():
        nonlocal remaining, failed
        window.editor.document().setModified(False)
        QApplication.clipboard().setImage(QImage(image_path))
        if not window.paste_image(replace_confirmed=True):
            failed = True
            Path(output).write_text(json.dumps({"error": window.status.text(), "input_route": "clipboard"}), encoding="utf-8")
            timer.stop()
            window.close()
            app.quit()
            return
        if pack_path:
            window.method_combo.setCurrentIndex(window.method_combo.findData(f"vision:{pack.id}"))
        elif neural_path:
            window.method_combo.setCurrentIndex(window.method_combo.findData(f"neural:{neural_pack.id}"))
        elif edition != "pocket":
            window.method_combo.setCurrentIndex(1)
        window.recognize()
        remaining -= 1

    def poll():
        nonlocal failed
        if window.worker:
            return
        if window.result is None:
            failed = True
            Path(output).write_text(json.dumps({"error": window.status.text()}), encoding="utf-8")
            timer.stop()
            window.close()
            app.quit()
            return
        measurements.append({"characters": len(window.result.text), "elapsed": window.result.elapsed,
                             "worker_peak_rss": window.result.peak_rss, "idle_rss": tree_rss()})
        if remaining > 0:
            run_next()
        else:
            Path(output).write_text(json.dumps({"iterations": measurements, "qt_platform": app.platformName(), "input_route": "clipboard"}), encoding="utf-8")
            timer.stop()
            window.close()
            app.quit()

    timer = QTimer()
    timer.timeout.connect(poll)
    timer.start(50)
    QTimer.singleShot(0, run_next)
    def timed_out():
        nonlocal failed
        failed = True
        timer.stop()
        if window.worker:
            window.worker.cancel.set()
            window.worker.wait(5000)
        Path(output).write_text(json.dumps({"error": "GUI workload timed out", "completed_iterations": len(measurements)}), encoding="utf-8")
        window.editor.document().setModified(False)
        window.close()
        app.quit()

    method = "vision" if pack_path else "neural" if neural_path else str(window.method_combo.currentData())
    deadline = gui_workload_timeout_seconds(method, backend=window.vision_backend, loops=loops)
    QTimer.singleShot(deadline * 1000, timed_out)
    app.exec()
    return 2 if failed else 0


def observe(command: list[str], output: Path, budget: int, timeout_seconds: int = 180, *, isolated: bool = False) -> dict:
    env = runtime_test_environment(output.parent / "runtime-العربية", isolated=isolated)
    env["QT_QPA_PLATFORM"] = gui_test_platform()
    env["XDG_CONFIG_HOME"] = str(output.parent / "config")
    env["APPDATA"] = str(output.parent / "config")
    start = time.monotonic()
    peak = 0
    timed_out = False
    with tempfile.TemporaryFile() as log:
        process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log, stderr=log)
        try:
            while process.poll() is None:
                peak = max(peak, tree_rss(process.pid))
                if time.monotonic() - start > timeout_seconds:
                    from ocready.core.memory import stop_tree
                    stop_tree(process.pid)
                    timed_out = True
                    break
                time.sleep(.01)
        finally:
            if process.poll() is None:
                from ocready.core.memory import stop_tree
                stop_tree(process.pid)
            process.wait()
        log.seek(0, os.SEEK_END)
        log.seek(max(0, log.tell() - 3000))
        error = log.read(3000).decode("utf-8", errors="replace")
    exit_code = process.returncode
    try:
        details = json.loads(output.read_text(encoding="utf-8"))
        if not isinstance(details, dict):
            raise ValueError("expected a result object")
    except (OSError, ValueError):
        details = {"error": "The process did not produce a valid benchmark result."}
        exit_code = exit_code or 2
    if timed_out:
        details["error"] = f"Benchmark scenario exceeded {timeout_seconds} seconds"
        exit_code = exit_code or 2
    if details.get("error"):
        exit_code = exit_code or 2
    return {"peak_rss_bytes": peak, "budget_bytes": budget, "below_budget": peak < budget,
            "elapsed_seconds": round(time.monotonic() - start, 3), "exit_code": exit_code,
            "details": details, "error": error if exit_code else "", "timeout_seconds": timeout_seconds, "timed_out": timed_out}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--edition", choices=["all", *EDITIONS], default="all")
    parser.add_argument("--output", type=Path, default=ROOT / "test-output" / "benchmarks.json")
    parser.add_argument("--binary", type=Path, help="Include onefile launcher overhead in headless scenarios")
    parser.add_argument("--method", choices=("tesseract-fast", "tesseract-best", "vision", "neural"),
                        help="Explicit embedded method; requires --binary")
    parser.add_argument("--pack-id", help="Explicit embedded vision/neural pack ID; requires --binary and --method")
    local = parser.add_mutually_exclusive_group()
    local.add_argument("--vision-pack", type=Path, help="Benchmark a local VLM pack instead of classical OCR")
    local.add_argument("--neural-pack", type=Path, help="Benchmark a local neural OCR pack")
    parser.add_argument("--gui-child", nargs=4, metavar=("IMAGE", "EDITION", "OUTPUT", "LOOPS"), help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.gui_child:
        image, edition, output, loops = args.gui_child
        return gui_child(image, edition, output, int(loops), args.vision_pack, args.neural_pack)
    editions = list(EDITIONS) if args.edition == "all" else [args.edition]
    binary_profile = json.loads((args.binary.parent / "build-manifest.json").read_text(encoding="utf-8")) if args.binary else None
    if binary_profile and editions != [binary_profile["edition"]]:
        parser.error("--edition must match the compiled binary's edition")
    if args.binary and (args.vision_pack or args.neural_pack):
        parser.error("Benchmark embedded packs through their binary's default method; pack paths are for source runs")
    if args.method and not args.binary or args.pack_id and (not args.binary or args.method not in {"vision", "neural"}):
        parser.error("Explicit methods/pack IDs require --binary; pack IDs also require --method vision or neural")
    selection = ["--method", args.method] if args.method else []
    if args.pack_id:
        selection += ["--pack-id", args.pack_id]
    source = source_record(ROOT)
    binary_hash = file_sha256(args.binary) if args.binary else None
    records = []
    with tempfile.TemporaryDirectory(prefix="ocready-benchmark-") as temporary:
        temporary = Path(temporary)
        for edition in editions:
            for scenario in ("sample", "dark", "max-pixels", "gui-onefile" if args.binary else "gui-repeated"):
                image = temporary / "input-العربية.png"
                output = temporary / "result.json"
                output.unlink(missing_ok=True)
                make_image(image, edition, dark=scenario == "dark", maximum=scenario in {"max-pixels", "gui-repeated", "gui-onefile"})
                base = [str(args.binary.resolve())] if args.binary else [sys.executable, "-m", "ocready"]
                command = [*base, str(image), "--json", "--layout", "sparse", "--edition", edition, "--output", str(output)]
                if selection:
                    command += selection
                elif args.vision_pack:
                    from ocready.core.models import load_pack
                    pack = load_pack(args.vision_pack)
                    command += ["--method", "vision", "--model-pack", str(args.vision_pack.resolve()), "--language", pack.languages]
                elif args.neural_pack:
                    from ocready.core.neural_packs import load_neural_pack
                    pack = load_neural_pack(args.neural_pack)
                    command += ["--method", "neural", "--neural-pack", str(args.neural_pack.resolve()), "--language", pack.languages]
                elif edition != "pocket" and (not binary_profile or "tesseract-best" in binary_profile["methods"]):
                    command += ["--method", "tesseract-best"]
                if scenario == "dark":
                    command.append("--invert")
                if scenario == "gui-repeated":
                    command = [sys.executable, str(Path(__file__).resolve()), "--gui-child", str(image), edition, str(output), "4"]
                    if args.vision_pack:
                        command += ["--vision-pack", str(args.vision_pack.resolve())]
                    elif args.neural_pack:
                        command += ["--neural-pack", str(args.neural_pack.resolve())]
                elif scenario == "gui-onefile":
                    command = [*base, str(image), "--edition", edition, "--ui-smoke-output", str(output), *selection]
                method = args.method or ("vision" if args.vision_pack else "neural" if args.neural_pack else
                                         binary_profile["methods"][0] if binary_profile else "tesseract-fast")
                deadline = observed_workload_timeout_seconds(method, loops=4 if scenario == "gui-repeated" else 1)
                result = observe(command, output, EDITIONS[edition].budget, timeout_seconds=deadline, isolated=bool(args.binary))
                result = {"edition": edition, "max_pixels": EDITIONS[edition].max_pixels, "scenario": scenario, **result}
                # Preserve evidence without copying all recognized document contents into reports.
                if "text" in result["details"]:
                    result["details"] = redact_details(result["details"])
                check_requested_engine(result, args.method, args.pack_id)
                records.append(result)
                print(f"{edition:9} {scenario:12} {result['peak_rss_bytes'] / 1e6:7.1f} MB  {'PASS' if result['below_budget'] and not result['exit_code'] else 'FAIL'}", flush=True)
    report = {"sample_interval_ms": 10, "rss_scope": "observed root plus all descendants; shared mappings may be counted more than once",
              "platform": sys.platform, "python": sys.version.split()[0], "cpu_count": psutil.cpu_count(),
              "binary": bool(args.binary), "scenarios": records,
              "execution_environment": execution_policy(bool(args.binary)),
              "source": source, "sources_changed_during_run": source_record(ROOT) != source,
              "binary_sha256": binary_hash,
              "binary_changed_during_run": bool(args.binary and file_sha256(args.binary) != binary_hash),
              "build_profile": binary_profile, "requested_method": args.method, "requested_pack_id": args.pack_id}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if (all(row["below_budget"] and row["exit_code"] == 0 for row in records)
                 and not report["sources_changed_during_run"] and not report["binary_changed_during_run"]) else 2


if __name__ == "__main__":
    raise SystemExit(main())
