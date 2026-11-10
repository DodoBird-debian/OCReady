import dataclasses
import json
import threading
from pathlib import Path

import pytest

from ocready.core.editions import EDITIONS
from ocready.core.models import ModelPack, load_pack, load_packs, save_packs
from ocready.core.process import ProcessResult
from ocready.core.types import BudgetExceeded, Cancelled, OCRError
from ocready.engines import vision


@pytest.fixture
def pack(tmp_path):
    model, projector, runner = (tmp_path / name for name in ("model.gguf", "mmproj.gguf", "runner"))
    model.write_bytes(b"GGUFmodel")
    projector.write_bytes(b"GGUFprojector")
    runner.write_text("test runner")
    return ModelPack("test", "Local test", str(runner), str(model), str(projector), memory_mb=2000)


def test_model_validation_and_admission(pack):
    pack.validate()
    assert pack.admission(EDITIONS["studio"])[0]
    assert not pack.admission(EDITIONS["pocket"])[0]
    assert dataclasses.replace(pack, memory_mb=500).admission(EDITIONS["everyday"])[0]
    assert not dataclasses.replace(pack, memory_mb=3799).admission(EDITIONS["studio"])[0]
    Path(pack.projector).write_bytes(b"not GGUF")
    with pytest.raises(OCRError, match="not a GGUF"):
        pack.validate()


def test_model_manifest_resolves_relative_paths(pack, tmp_path):
    record = pack.to_dict()
    for key in ("runner", "model", "projector"):
        record[key] = Path(record[key]).name
    path = tmp_path / "pack.json"
    path.write_text(json.dumps(record))
    loaded = load_pack(path)
    assert loaded.model == pack.model
    loaded.validate()


def test_config_persists_only_model_configuration(pack, tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path))
    save_packs([pack])
    assert load_packs() == [pack]


@pytest.mark.parametrize("bad", [{}, {"id": []}, {"id": "x", "name": "x", "runner": "x", "model": "x", "projector": "x", "tokens": "512"}])
def test_malformed_model_configuration(bad):
    with pytest.raises(OCRError):
        ModelPack.from_dict(bad)


def test_cpu_command_disables_all_gpu_offload(pack):
    args = vision.command(pack, Path("image.png"), cuda=False)
    assert args[args.index("-ngl") + 1] == "0"
    assert "--no-mmproj-offload" in args
    assert args[args.index("-n") + 1] == "512"


def test_auto_can_accelerate_with_the_same_runner(pack, tmp_path, monkeypatch):
    monkeypatch.setattr(vision, "has_cuda", lambda runner, *_args: runner == pack.runner)
    calls = []
    def fake_run(args, **kwargs):
        calls.append(args)
        return ProcessResult("Read text", "", 700_000_000, 1)
    monkeypatch.setattr(vision, "run_process", fake_run)
    result = vision.recognize(tmp_path / "image.png", EDITIONS["studio"], pack)
    assert calls[0][0] == pack.runner
    assert calls[0][calls[0].index("-ngl") + 1] == "99"
    assert result.backend == "CUDA"


def test_english_only_model_does_not_silently_claim_arabic(pack, tmp_path):
    with pytest.raises(OCRError, match="configured for eng"):
        vision.recognize(tmp_path / "image.png", EDITIONS["studio"], dataclasses.replace(pack, languages="eng"))


def test_cuda_initialization_failure_retries_cpu(pack, tmp_path, monkeypatch):
    calls = []
    pack = dataclasses.replace(pack, cuda_runner=pack.runner)
    monkeypatch.setattr(vision, "has_cuda", lambda *args: True)
    def fake_run(args, **kwargs):
        calls.append(args)
        if len(calls) == 1:
            raise OCRError("CUDA initialization failed")
        return ProcessResult("مرحبا بالعالم", "", 1_800_000_000, 2.5)
    monkeypatch.setattr(vision, "run_process", fake_run)
    result = vision.recognize(tmp_path / "image.png", EDITIONS["studio"], pack)
    assert len(calls) == 2
    assert "--no-mmproj-offload" in calls[1]
    assert result.backend == "CPU"
    assert not result.words
    assert result.confidence is None
    assert "retried on CPU" in result.note


@pytest.mark.parametrize("error", [Cancelled("cancelled"), BudgetExceeded("budget")])
def test_cancellation_or_budget_never_retried_as_cpu(pack, tmp_path, monkeypatch, error):
    calls = []
    pack = dataclasses.replace(pack, cuda_runner=pack.runner)
    monkeypatch.setattr(vision, "has_cuda", lambda *args: True)
    def fake_run(*args, **kwargs):
        calls.append(args)
        raise error
    monkeypatch.setattr(vision, "run_process", fake_run)
    with pytest.raises(type(error)):
        vision.recognize(tmp_path / "image.png", EDITIONS["studio"], pack, cancel=threading.Event())
    assert len(calls) == 1


def test_vision_cleanup_preserves_recognized_content():
    assert vision.clean_output("\x1b[31mمرحبا<|im_end|>\n") == "مرحبا"
    assert vision.clean_output("[Document title]\nA sentence.") == "[Document title]\nA sentence."
