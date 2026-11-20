import dataclasses
import json
import threading

import pytest

from ocready.__main__ import main
from ocready.core.editions import EDITIONS
from ocready.core.models import ModelPack
from ocready.core.process import ProcessResult
from ocready.core.types import Cancelled, OCRError
from ocready.engines import vision_checks
from ocready.engines.vision_adapters import get_adapter


@pytest.mark.parametrize("stdout,stderr,expected", [
    ("Available devices:\n  CUDA0: NVIDIA Example (8192 MiB, 7000 MiB free)\n", "", True),
    ("Available devices:\n  (none)\n", "CUDA0: driver initialization failed", False),
    ("Available devices:\n  (none)\n", "loaded /cuda/libcuda.so", False),
    ("Available devices:\n  CUDA0: no device\n", "", False),
    ("Available devices:\n  CUDA0: Example (0 MiB, 0 MiB free)\n", "", False),
    ("Available devices:\n  Vulkan0: Example (8192 MiB, 7000 MiB free)\n", "CUDA : found library", False),
])
def test_device_discovery_requires_an_actual_stdout_device_row(stdout, stderr, expected):
    assert get_adapter("llama.cpp").probe_cuda(stdout, stderr) is expected


@pytest.fixture
def pack(tmp_path):
    assets = [tmp_path / name for name in ("runner", "model.gguf", "projector.gguf")]
    for path in assets:
        path.write_bytes(b"GGUFtest")
    return ModelPack("checks", "Checks", *(str(path) for path in assets), memory_mb=500)


def test_diagnostic_reuses_probe_but_never_claims_inference_verified(pack, monkeypatch):
    calls = []
    def execute(command, **kwargs):
        calls.append((command, kwargs))
        return ProcessResult("Available devices:\nCUDA0: Example (8192 MiB, 7000 MiB free)\n", "", 1, 0.1)
    monkeypatch.setattr(vision_checks, "run_process", execute)
    result = vision_checks.check_model_backends(pack, EDITIONS["everyday"])
    assert len(calls) == 1 and calls[0][0] == [pack.runner, "--list-devices"]
    assert calls[0][1]["budget"] == 1_000_000_000 and calls[0][1]["timeout"] == 20
    assert result["cpu_available"] and result["cuda_device_detected"]
    assert result["can_attempt_inference"] and not result["inference_verified"]
    assert result["automatic_backend"] == "CUDA"


def test_missing_helper_and_invalid_weights_are_independent_diagnostics(pack, tmp_path, monkeypatch):
    (tmp_path / "model.gguf").write_bytes(b"invalid")
    monkeypatch.setattr(vision_checks, "run_process", lambda *_a, **_k: ProcessResult("Available devices:\n(none)", "", 1, 0.1))
    result = vision_checks.check_model_backends(dataclasses.replace(pack, cuda_runner=str(tmp_path / "missing")), EDITIONS["everyday"])
    assert result["cpu_available"] and not result["assets_valid"]
    assert result["cuda_runner"]["status"] == "missing"
    assert not result["can_attempt_inference"] and result["automatic_backend"] == "CPU"


def test_cuda_only_json_worker_is_not_advertised_as_cpu_fallback(pack, monkeypatch):
    pack = dataclasses.replace(pack, adapter="json-cli-v1")
    monkeypatch.setattr(vision_checks, "run_process", lambda *_a, **_k: ProcessResult('{"schema":1,"backends":["cuda"]}', "", 1, 0.1))
    result = vision_checks.check_model_backends(pack, EDITIONS["everyday"])
    assert result["cuda_device_detected"] and not result["cpu_available"]
    assert not result["can_attempt_inference"] and result["automatic_backend"] == "unavailable"


def test_probe_failure_is_reported_and_cancellation_propagates(pack, monkeypatch):
    def fail(*_a, **_k):
        raise OCRError("Could not start runner")
    monkeypatch.setattr(vision_checks, "run_process", fail)
    assert vision_checks.check_model_backends(pack, EDITIONS["studio"])["cpu_runner"]["status"] == "failed"
    def cancel(*_a, **_k):
        raise Cancelled("cancelled")
    monkeypatch.setattr(vision_checks, "run_process", cancel)
    with pytest.raises(Cancelled):
        vision_checks.check_model_backends(pack, EDITIONS["studio"], cancel=threading.Event())


def test_headless_backend_checks_resolve_external_manifest_without_inference(pack, tmp_path, monkeypatch, capsys):
    manifest = tmp_path / "pack.json"
    manifest.write_text(json.dumps(pack.to_dict()), encoding="utf-8")
    monkeypatch.setattr(vision_checks, "run_process", lambda *_a, **_k: ProcessResult("Available devices:\n(none)", "", 1, 0.1))
    assert main(["--check-backends", "--model-pack", str(manifest), "--edition", "everyday"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["edition"] == "everyday" and report["backend_checks"][0]["cpu_available"]
    assert main(["image.png", "--check-backends"]) == 2
    assert "without an image" in capsys.readouterr().err
