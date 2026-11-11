"""Measure native CPU VLM feasibility before considering a smaller app edition.

The default measures workers separately. Optional Qt workspace mode includes
source-app/clipboard buffers, but neither mode includes a onefile launcher or
enables an unsupported production method. A small worker is not a RAM certificate.
"""
import argparse
import json
import os
import subprocess
import tempfile
import time
from contextlib import contextmanager, nullcontext
from pathlib import Path

from ocready.core.memory import stop_tree, tree_rss
from ocready.core.models import load_pack
from ocready.engines.vision import command, runner_env
from ocready.engines.vision_adapters import clean_llama_output
from scripts.accuracy import error_metrics
from scripts.corpus_identity import load_corpus_identity
from scripts.host_diagnostics import host_identity
from scripts.provenance import file_sha256, require_unchanged, source_record

ROOT = Path(__file__).resolve().parents[1]


@contextmanager
def qt_workspace():
    from PySide6.QtWidgets import QApplication

    from ocready.ui.theme import apply_theme
    from ocready.ui.window import MainWindow
    with tempfile.TemporaryDirectory(prefix="ocready-vision-workspace-") as temporary:
        original = {key: os.environ.get(key) for key in ("XDG_CONFIG_HOME", "APPDATA")}
        os.environ.update(XDG_CONFIG_HOME=temporary, APPDATA=temporary)
        window = None
        try:
            app = QApplication.instance() or QApplication([])
            apply_theme(app)
            window = MainWindow(edition="pocket")
            window.setWindowTitle("OCReady vision feasibility · experimental source workspace")
            window.show()
            app.processEvents()
            yield app, window
        finally:
            if window is not None:
                window.editor.document().setModified(False)
                window.close()
            for key, value in original.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


def measure(args: list[str], runner: str, *, timeout_seconds: float = 120, worker_limit: int = 1_000_000_000,
            process_events=None) -> dict:
    started = time.monotonic()
    peak, experiment_peak, failure, terminated = 0, tree_rss(), "", False
    with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as error:
        try:
            child = subprocess.Popen(args, stdout=output, stderr=error, env=runner_env(runner))
        except OSError as exc:
            return {"exit_code": None, "error": f"Could not start the component worker: {exc}",
                    "terminated_by_probe": False,
                    "worker_tree_peak_rss_bytes": 0, "experiment_tree_peak_rss_bytes": experiment_peak,
                    "elapsed_seconds": round(time.monotonic() - started, 3),
                    "text": "", "stderr_tail": ""}
        try:
            while child.poll() is None:
                peak = max(peak, tree_rss(child.pid))
                experiment_peak = max(experiment_peak, tree_rss())
                if peak > worker_limit:
                    failure = f"Component experiment stopped above {worker_limit} bytes worker-tree RSS."
                elif time.monotonic() - started > timeout_seconds:
                    failure = f"Component experiment exceeded its {timeout_seconds:g}-second deadline."
                elif max(output.tell(), error.tell()) > 8_000_000:
                    failure = "Component experiment produced excessive diagnostic output."
                if failure:
                    break
                if process_events is not None:
                    process_events()
                time.sleep(.01)
        finally:
            if child.poll() is None:
                terminated = True
                stop_tree(child.pid)
            child.wait()
        output.seek(0)
        error.seek(0, 2)
        error.seek(max(0, error.tell() - 16000))
        text = clean_llama_output(output.read(8_000_000).decode("utf-8", errors="replace"))
        # psutil's cleanup can reap a terminated POSIX child before Popen; do
        # not present Popen's resulting fallback zero as a successful exit.
        return {"exit_code": None if terminated else child.returncode, "terminated_by_probe": terminated,
                "error": failure, "worker_tree_peak_rss_bytes": peak,
                "experiment_tree_peak_rss_bytes": experiment_peak,
                "elapsed_seconds": round(time.monotonic() - started, 3), "text": text,
                "stderr_tail": error.read(16000).decode("utf-8", errors="replace")}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path, required=True)
    parser.add_argument("--candidate-projector", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--qt-workspace", action="store_true", help="Retain the source Pocket workspace and real clipboard buffers while observing the experimental worker")
    args = parser.parse_args()
    pack = load_pack(args.pack)
    pack.validate()
    if pack.adapter != "llama.cpp" or "eng" not in pack.languages.split("+"):
        parser.error("This component probe requires a native llama.cpp pack supporting English.")
    candidate = args.candidate_projector.resolve()
    with candidate.open("rb") as stream:
        if stream.read(4) != b"GGUF":
            parser.error("Choose a derived GGUF projector for comparison.")
    source = source_record(ROOT)
    corpus, corpus_sha, _legacy = load_corpus_identity(ROOT / "assets/accuracy/manifest.json")
    english = next(case for case in corpus["cases"] if case["id"] == "english-ui")
    fixture = ROOT / "assets/accuracy" / english["image"]
    if file_sha256(fixture) != english["image_sha256"]:
        raise ValueError("The English fixture differs from the corpus manifest.")
    report = {"scope": __doc__, "source": source, "host": host_identity(), "sample_interval_ms": 10,
              "qt_workspace": args.qt_workspace, "onefile": False,
              "rss_scopes": {"worker": "Native worker and descendants only", "experiment": "Probe process and descendants, including source Qt/clipboard buffers only in Qt workspace mode"},
              "timeout_seconds_per_case": 120, "worker_rss_guard_bytes": 1_000_000_000,
              "pack_id": pack.id, "languages": pack.languages, "corpus_content_sha256": corpus_sha,
              "assets": {key: {"sha256": file_sha256(Path(value)), "bytes": Path(value).stat().st_size}
                         for key, value in {"runner": pack.runner, "model": pack.model,
                                            "original_projector": pack.projector, "candidate_projector": str(candidate)}.items()},
              "cases": []}
    variants = [("baseline", pack.projector, 4096, "f16", 256, 128),
                ("short-context", pack.projector, 1024, "f16", 256, 128),
                ("candidate-projector", str(candidate), 1024, "f16", 256, 128),
                ("candidate-small-batch", str(candidate), 1024, "f16", 128, 64),
                ("candidate-q8-cache", str(candidate), 1024, "q8_0", 128, 64)]
    with qt_workspace() if args.qt_workspace else nullcontext(None) as workspace:
        if workspace:
            report["qt_platform"] = workspace[0].platformName()
        for label, projector, context, cache, batch, ubatch in variants:
            for name, image, expected in (("bilingual-sample-English-only", ROOT / "assets/sample-bilingual.png", None),
                                          ("english-ui", fixture, english["expected"])):
                if workspace:
                    from PySide6.QtGui import QImage
                    app, window = workspace
                    window.editor.document().setModified(False)
                    app.clipboard().setImage(QImage(str(image)))
                    if not window.paste_image():
                        raise RuntimeError("The owned Qt workspace could not paste its fixture.")
                    app.processEvents()
                native = command(pack, image, cuda=False)
                for flag, value in (("--mmproj", projector), ("-c", context), ("-b", batch), ("-ub", ubatch)):
                    native[native.index(flag) + 1] = str(value)
                native += ["-ctk", cache, "-ctv", cache]
                result = measure(native, pack.runner, process_events=workspace[0].processEvents if workspace else None)
                result.update(variant=label, fixture=name, image_sha256=file_sha256(image),
                              context=context, cache_type=cache, batch=batch, micro_batch=ubatch)
                if expected is not None:
                    result["accuracy"] = error_metrics(expected, result["text"])
                if workspace:
                    workspace[1].editor.setPlainText(result["text"])
                    workspace[0].processEvents()
                report["cases"].append(result)
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                print(json.dumps({key: value for key, value in result.items() if key not in {"stderr_tail", "text"}}, ensure_ascii=True), flush=True)
    require_unchanged(ROOT, source)
    if any(case["exit_code"] or case["error"] or not case["text"] for case in report["cases"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
