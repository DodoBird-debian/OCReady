import dataclasses
import io
import json
import tarfile
from pathlib import Path

import pytest
from PIL import Image

from ocready.core.editions import EDITIONS
from ocready.core.models import ModelPack, load_pack
from ocready.core.process import ProcessResult
from ocready.core.types import BudgetExceeded, Cancelled, OCRError
from ocready.engines import vision
from ocready.engines.vision_adapters import get_adapter
from scripts.bundle_models import bundle_pack


@pytest.fixture
def json_pack(tmp_path):
    runner = tmp_path / "worker"
    runner.write_bytes(b"test runner")
    model = tmp_path / "model.onnx"
    model.write_bytes(b"opaque model weights")
    image = tmp_path / "input.png"
    Image.new("RGB", (100, 80), "white").save(image)
    return ModelPack("json-test", "JSON worker", str(runner), str(model), "", adapter="json-cli-v1", memory_mb=500), image


def response(**changes):
    return json.dumps({"schema": 1, "width": 100, "height": 80, "text": "مرحبا بالعالم\nOrder ٢٥٠٠", "backend": "CPU", **changes})


def test_old_packs_keep_llama_defaults_and_unknown_adapters_fail(json_pack):
    pack, _image = json_pack
    data = pack.to_dict()
    data.pop("adapter")
    assert ModelPack.from_dict(data).adapter == "llama.cpp"
    with pytest.raises(OCRError, match="Unsupported vision runtime"):
        ModelPack.from_dict({**data, "adapter": "arbitrary.python.module"})
    with pytest.raises(OCRError, match="require.*projector"):
        dataclasses.replace(pack, adapter="llama.cpp").validate()


def test_json_adapter_runs_through_shared_engine_without_gguf_or_projector(json_pack, monkeypatch):
    pack, image = json_pack
    calls = []
    def execute(args, **kwargs):
        calls.append((args, kwargs))
        return ProcessResult(response(), "", 350_000_000, 1)
    monkeypatch.setattr(vision, "run_process", execute)
    result = vision.recognize(image, EDITIONS["everyday"], pack, backend="cpu")
    assert result.text == "مرحبا بالعالم\nOrder ٢٥٠٠"
    assert result.runtime == "json-cli-v1" and result.backend == "CPU"
    assert not result.words and result.geometry == "none"
    args, kwargs = calls[0]
    assert "--ocready-vision-v1" in args and "--projector" not in args
    assert kwargs["budget"] == EDITIONS["everyday"].budget


@pytest.mark.parametrize("changes", [{"schema": True}, {"schema": 2}, {"text": 4}, {"backend": {}},
                                      {"width": True}, {"width": 101}, {"note": []}, {"backend": "CUDA"}])
def test_json_adapter_rejects_malformed_or_wrong_image_responses(json_pack, changes):
    _pack, image = json_pack
    with pytest.raises(OCRError):
        get_adapter("json-cli-v1").decode(response(**changes), image, False)


def test_json_worker_backend_fallback_is_reported_exactly(json_pack, monkeypatch):
    pack, image = json_pack
    monkeypatch.setattr(vision, "has_cuda", lambda *_args: True)
    monkeypatch.setattr(vision, "run_process", lambda *_args, **_kwargs: ProcessResult(response(), "", 350_000_000, 1))
    result = vision.recognize(image, EDITIONS["everyday"], pack, backend="cuda")
    assert result.backend == "CPU" and "reported CPU fallback" in result.note


@pytest.mark.parametrize("error", [Cancelled("cancelled"), BudgetExceeded("budget")])
def test_json_adapter_does_not_retry_cancellation_or_budget_failure(json_pack, monkeypatch, error):
    pack, image = json_pack
    calls = []
    monkeypatch.setattr(vision, "has_cuda", lambda *_args: True)
    def execute(*args, **_kwargs):
        calls.append(args)
        raise error
    monkeypatch.setattr(vision, "run_process", execute)
    with pytest.raises(type(error)):
        vision.recognize(image, EDITIONS["everyday"], pack)
    assert len(calls) == 1


def test_json_capability_probe_requires_versioned_backend_declaration():
    adapter = get_adapter("json-cli-v1")
    assert adapter.probe_cuda('{"schema":1,"backends":["cpu","cuda"]}', "")
    assert not adapter.probe_cuda('{"schema":1,"backends":["cpu"]}', "")
    for malformed in ['{"schema":1,"backends":[{}]}', '{"schema":1,"backends":[]}', 'CUDA0', '[]']:
        with pytest.raises(OCRError):
            adapter.probe_cuda(malformed, "")


def test_json_pack_embedding_preserves_adapter_and_opaque_format(json_pack, tmp_path):
    pack, _image = json_pack
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w") as archive:
        metadata = bundle_pack(archive, pack)
    stream.seek(0)
    with tarfile.open(fileobj=stream) as archive:
        archive.extractall(tmp_path / "out", filter="data")
    loaded = load_pack(tmp_path / "out/vision/json-test/pack.json")
    loaded.validate()
    assert loaded.adapter == "json-cli-v1" and loaded.projector == ""
    assert Path(loaded.model).suffix == ".onnx"
    assert metadata["adapter"] == "json-cli-v1"
