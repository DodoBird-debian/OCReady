"""Qualify actual CPU packs and a relocated compiled JSON worker on this host.

This is source/standalone-worker evidence, not a full onefile or accuracy
certification. Failures remain in the report and never stop later model probes.
"""
import argparse
import dataclasses
import json
import os
import shutil
import tempfile
from pathlib import Path

from ocready.core.editions import EDITIONS
from ocready.core.images import load_image
from ocready.core.models import load_pack
from ocready.core.pipeline import Request, recognize_image
from ocready.core.process import run_process
from ocready.engines.vision_adapters import get_adapter
from ocready.engines.vision_checks import check_model_backends
from scripts.accuracy import DEFAULT_CORPUS, error_metrics
from scripts.benchmark import local_pack_identity
from scripts.host_diagnostics import host_identity
from scripts.packaged_environment import runtime_test_environment
from scripts.provenance import file_sha256, source_record
from scripts.verify_vision_worker import verify_worker

ROOT = Path(__file__).resolve().parents[1]


def probe_pack(path: Path, worker: Path, temporary: Path, corpus: dict, case_id: str = "english-ui") -> dict:
    identity = local_pack_identity(path, None)
    pack = dataclasses.replace(load_pack(path), cuda_runner="")
    pack.validate(require_cuda=False)
    if pack.adapter != "llama.cpp":
        raise ValueError("Supply native llama.cpp packs for paired native/JSON qualification.")
    case = next(case for case in corpus["cases"] if case["id"] == case_id)
    image = DEFAULT_CORPUS.parent / case["image"]
    if file_sha256(image) != case["image_sha256"] or not set(case["language"].split("+")) <= set(pack.languages.split("+")):
        raise ValueError("The fixture changed or the pack does not declare its languages.")
    checks = check_model_backends(pack, EDITIONS["studio"])
    if not checks["can_attempt_inference"]:
        raise ValueError("CPU runner/admission checks failed: " + json.dumps(checks, ensure_ascii=True))
    native, _ = recognize_image(load_image(image, EDITIONS["studio"]),
                                Request(EDITIONS["studio"], language=case["language"], method="vision", model_pack=pack, backend="cpu"))
    if native.engine != f"vision:{pack.id}" or native.backend != "CPU":
        raise ValueError("The native CPU request returned the wrong model/backend.")
    unavailable_cuda = None
    if not checks["cuda_device_detected"]:
        fallback, _ = recognize_image(load_image(image, EDITIONS["studio"]),
                                      Request(EDITIONS["studio"], language=case["language"], method="vision", model_pack=pack, backend="cuda"))
        if fallback.engine != native.engine or fallback.backend != "CPU" or "CUDA was unavailable" not in fallback.note:
            raise ValueError("The configured runtime's unavailable CUDA did not produce an explicit CPU fallback.")
        unavailable_cuda = {"result": fallback.to_dict(), "metrics": error_metrics(case["expected"], fallback.text)}
    bridge_pack = dataclasses.replace(pack, runner=str(worker), adapter="json-cli-v1")
    adapter = get_adapter(bridge_pack.adapter)
    environment = runtime_test_environment(temporary / "runtime-العربية", isolated=True)
    capability = run_process(adapter.probe_command(str(worker)), budget=EDITIONS["studio"].budget,
                             timeout=30, env=environment, cwd=temporary)
    if "cpu" not in adapter.probe_backends(capability.stdout, capability.stderr):
        raise ValueError("The relocated worker did not declare CPU support.")
    result = run_process(adapter.command(bridge_pack, image, False), budget=EDITIONS["studio"].budget,
                         timeout=300, env=environment, cwd=temporary)
    read = adapter.decode(result.stdout, image, False)
    if local_pack_identity(path, None) != identity:
        raise ValueError("Model manifest/assets changed during qualification.")
    return {"status": "completed", "pack": identity, "fixture_sha256": case["image_sha256"],
            "fixture_id": case["id"], "language": case["language"], "expected": case["expected"], "checks": checks,
            "native": {"result": native.to_dict(), "metrics": error_metrics(case["expected"], native.text)},
            "unavailable_cuda_fallback": unavailable_cuda,
            "compiled_json": {"text": read.text, "backend": read.backend, "peak_rss": result.peak_rss,
                              "elapsed": result.elapsed, "containment": result.containment,
                              "metrics": error_metrics(case["expected"], read.text)}}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path, action="append", required=True)
    parser.add_argument("--worker", type=Path, required=True, help="Verified compiled CPU worker distribution directory")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = source_record(ROOT)
    report = {"scope": "Native CPU source + relocated compiled JSON worker; English fixture plus a bilingual fixture for Arabic/English models. Unavailable-runtime CUDA preference must fall back to CPU. No outer onefile, GPU or broad accuracy certification.",
              "source": source, "host": host_identity(), "models": []}
    try:
        report["worker_manifest"] = verify_worker(args.worker)
        corpus = json.loads(DEFAULT_CORPUS.read_text(encoding="utf-8"))
        report["corpus_sha256"] = file_sha256(DEFAULT_CORPUS)
        with tempfile.TemporaryDirectory(prefix="ocready-vlm-qualification-") as temporary:
            temporary = Path(temporary)
            folder = temporary / "worker-العربية"
            shutil.copytree(args.worker, folder, symlinks=True)
            verify_worker(folder)
            worker = folder / ("ocready-vision-bridge.exe" if os.name == "nt" else "ocready-vision-bridge")
            for path in args.pack:
                try:
                    result = probe_pack(path, worker, temporary, corpus)
                    if {"ara", "eng"} <= set(load_pack(path).languages.split("+")):
                        result["additional_fixtures"] = [probe_pack(path, worker, temporary, corpus, "bilingual-ui")]
                except Exception as exc:
                    result = {"status": "error", "manifest_name": f"{path.parent.name}/{path.name}", "error": str(exc)[-3000:]}
                report["models"].append(result)
                print(path.parent.name, result["status"], flush=True)
            verify_worker(folder)
    except Exception as exc:
        report["error"] = str(exc)[-3000:]
    report["sources_changed_during_run"] = source_record(ROOT) != source
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if (not report.get("error") and not report["sources_changed_during_run"]
                 and len(report["models"]) == len(args.pack)
                 and all(row["status"] == "completed" for row in report["models"])) else 2


if __name__ == "__main__":
    raise SystemExit(main())
