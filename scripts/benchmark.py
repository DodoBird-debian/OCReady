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

ROOT = Path(__file__).resolve().parents[1]


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


def gui_child(image_path: str, edition: str, output: str, loops: int, pack_path: Path | None = None) -> int:
    from PySide6.QtCore import QTimer
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
    window.show()
    remaining = loops
    measurements = []
    failed = False

    def run_next():
        nonlocal remaining
        window.editor.document().setModified(False)
        window.open_path(image_path)
        if pack_path:
            window.method_combo.setCurrentIndex(window.method_combo.findData(f"vision:{pack.id}"))
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
            Path(output).write_text(json.dumps({"iterations": measurements}), encoding="utf-8")
            timer.stop()
            window.close()
            app.quit()

    timer = QTimer()
    timer.timeout.connect(poll)
    timer.start(50)
    QTimer.singleShot(0, run_next)
    QTimer.singleShot(120_000, app.quit)
    app.exec()
    return 2 if failed else 0


def observe(command: list[str], output: Path, budget: int) -> dict:
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["XDG_CONFIG_HOME"] = str(output.parent / "config")
    env["APPDATA"] = str(output.parent / "config")
    start = time.monotonic()
    peak = 0
    with tempfile.TemporaryFile() as log:
        process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log, stderr=log)
        try:
            while process.poll() is None:
                peak = max(peak, tree_rss(process.pid))
                if time.monotonic() - start > 180:
                    from ocready.core.memory import stop_tree
                    stop_tree(process.pid)
                    raise RuntimeError("Benchmark scenario exceeded 180 seconds")
                time.sleep(.01)
        finally:
            process.wait()
        log.seek(0)
        error = log.read()[-3000:].decode("utf-8", errors="replace")
    details = json.loads(output.read_text(encoding="utf-8")) if output.exists() else {"error": error}
    return {"peak_rss_bytes": peak, "budget_bytes": budget, "below_budget": peak < budget,
            "elapsed_seconds": round(time.monotonic() - start, 3), "exit_code": process.returncode,
            "details": details, "error": error if process.returncode else ""}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--edition", choices=["all", *EDITIONS], default="all")
    parser.add_argument("--output", type=Path, default=ROOT / "test-output" / "benchmarks.json")
    parser.add_argument("--binary", type=Path, help="Include onefile launcher overhead in headless scenarios")
    parser.add_argument("--vision-pack", type=Path, help="Benchmark a local VLM pack instead of classical OCR")
    parser.add_argument("--gui-child", nargs=4, metavar=("IMAGE", "EDITION", "OUTPUT", "LOOPS"), help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.gui_child:
        image, edition, output, loops = args.gui_child
        return gui_child(image, edition, output, int(loops), args.vision_pack)
    editions = list(EDITIONS) if args.edition == "all" else [args.edition]
    binary_profile = json.loads((args.binary.parent / "build-manifest.json").read_text(encoding="utf-8")) if args.binary else None
    if binary_profile and editions != [binary_profile["edition"]]:
        parser.error("--edition must match the compiled binary's edition")
    if args.binary and args.vision_pack:
        parser.error("Benchmark embedded vision packs through their binary's default method; --vision-pack is for source runs")
    records = []
    with tempfile.TemporaryDirectory(prefix="ocready-benchmark-") as temporary:
        temporary = Path(temporary)
        for edition in editions:
            for scenario in ("sample", "dark", "max-pixels", "gui-onefile" if args.binary else "gui-repeated"):
                image = temporary / "input.png"
                output = temporary / "result.json"
                output.unlink(missing_ok=True)
                make_image(image, edition, dark=scenario == "dark", maximum=scenario in {"max-pixels", "gui-repeated", "gui-onefile"})
                base = [str(args.binary.resolve())] if args.binary else [sys.executable, "-m", "ocready"]
                command = [*base, str(image), "--json", "--layout", "sparse", "--edition", edition, "--output", str(output)]
                if args.vision_pack:
                    from ocready.core.models import load_pack
                    pack = load_pack(args.vision_pack)
                    command += ["--method", "vision", "--model-pack", str(args.vision_pack.resolve()), "--language", pack.languages]
                elif edition != "pocket" and (not binary_profile or "tesseract-best" in binary_profile["methods"]):
                    command += ["--method", "tesseract-best"]
                if scenario == "dark":
                    command.append("--invert")
                if scenario == "gui-repeated":
                    command = [sys.executable, str(Path(__file__).resolve()), "--gui-child", str(image), edition, str(output), "4"]
                    if args.vision_pack:
                        command += ["--vision-pack", str(args.vision_pack.resolve())]
                elif scenario == "gui-onefile":
                    command = [*base, str(image), "--edition", edition, "--ui-smoke-output", str(output)]
                result = observe(command, output, EDITIONS[edition].budget)
                result = {"edition": edition, "max_pixels": EDITIONS[edition].max_pixels, "scenario": scenario, **result}
                # Preserve evidence without copying all recognized document contents into reports.
                if "text" in result["details"]:
                    details = result["details"].get("result", result["details"])
                    result["details"] = {key: details[key] for key in ("elapsed", "peak_rss", "engine", "backend", "containment", "worker_limit", "worker_peak") if key in details}
                    result["details"]["words"] = len(details.get("words", []))
                records.append(result)
                print(f"{edition:9} {scenario:12} {result['peak_rss_bytes'] / 1e6:7.1f} MB  {'PASS' if result['below_budget'] and not result['exit_code'] else 'FAIL'}", flush=True)
    report = {"sample_interval_ms": 10, "rss_scope": "observed root plus all descendants; shared mappings may be counted more than once",
              "platform": sys.platform, "python": sys.version.split()[0], "cpu_count": psutil.cpu_count(),
              "binary": bool(args.binary), "scenarios": records}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if all(row["below_budget"] and row["exit_code"] == 0 for row in records) else 2


if __name__ == "__main__":
    raise SystemExit(main())
