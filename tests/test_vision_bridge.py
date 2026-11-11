import dataclasses
import io
import json
import os
import subprocess
import tarfile
from pathlib import Path

import pytest
from PIL import Image

from native import vision_bridge
from ocready.core.models import ModelPack, load_pack
from scripts.build_vision_bridge import copy_runtime
from scripts.bundle_models import bundle_pack
from scripts.provenance import file_sha256


def test_reference_worker_protocol_preserves_arabic_and_cpu_request(tmp_path, monkeypatch, capsys):
    runner = tmp_path / "llama-mtmd-cli"
    runner.write_bytes(b"native runner")
    image = tmp_path / "input.png"
    Image.new("RGB", (100, 80), "white").save(image)
    monkeypatch.setattr(vision_bridge, "runner_path", lambda: runner)
    calls = []
    def execute(args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, "مرحبا بالعالم<|im_end|>".encode(), b"")
    monkeypatch.setattr(vision_bridge.subprocess, "run", execute)
    assert vision_bridge.main(["--ocready-vision-v1", "--image", str(image), "--model", "model.gguf",
                               "--projector", "projector.gguf", "--prompt", "Read it", "--backend", "cpu"]) == 0
    response = json.loads(capsys.readouterr().out)
    assert response == {"schema": 1, "width": 100, "height": 80, "text": "مرحبا بالعالم", "backend": "CPU"}
    assert calls[0][calls[0].index("-ngl") + 1] == "0"
    assert "--no-mmproj-offload" in calls[0]
    monkeypatch.setattr(vision_bridge.subprocess, "run", lambda args, **_kwargs:
                        subprocess.CompletedProcess(args, 17, b"", b"x" * 20000))
    assert vision_bridge.main(["--ocready-vision-v1", "--image", str(image), "--model", "model.gguf",
                               "--projector", "projector.gguf", "--prompt", "Read it"]) == 2
    error = capsys.readouterr().err
    assert "Native vision runner exited with code 17" in error[-1600:]
    assert len(error) < 17000
    image.write_bytes(b"not an image")
    assert vision_bridge.main(["--ocready-vision-v1", "--image", str(image), "--model", "model.gguf",
                               "--projector", "projector.gguf", "--prompt", "Read it"]) == 2


def test_runtime_copy_removes_stale_gpu_libraries(tmp_path):
    source, target = tmp_path / "source", tmp_path / "worker/llama"
    source.mkdir()
    target.mkdir(parents=True)
    runner = source / "llama-mtmd-cli"
    runner.write_bytes(b"CPU executable")
    (source / "engine.so").write_bytes(b"CPU library")
    os.link(source / "engine.so", source / "engine.so.1")
    (target / "stale-cuda.so").write_bytes(b"old GPU library")
    copy_runtime(runner, target)
    assert (target / runner.name).read_bytes() == runner.read_bytes()
    assert not (target / "stale-cuda.so").exists()
    assert (target / "engine.so").stat().st_ino == (target / "engine.so.1").stat().st_ino


def test_json_standalone_embedding_preserves_declared_native_descendants(tmp_path):
    worker = tmp_path / "worker"
    (worker / "llama").mkdir(parents=True)
    runner = worker / "ocready-vision-bridge"
    runner.write_bytes(b"bridge")
    (worker / "llama/llama-mtmd-cli").write_bytes(b"native descendant")
    metadata = {"protocol": 1, "adapter": "json-cli-v1", "files": {p.relative_to(worker).as_posix(): file_sha256(p)
                 for p in worker.rglob("*") if p.is_file()}}
    (worker / "vision-build.json").write_text(json.dumps(metadata))
    (worker / "unrelated-private.txt").write_text("do not bundle")
    model = tmp_path / "model.gguf"
    model.write_bytes(b"GGUFmodel")
    pack = ModelPack("bridge", "Bridge", str(runner), str(model), "", adapter="json-cli-v1")
    payload = io.BytesIO()
    with tarfile.open(fileobj=payload, mode="w") as archive:
        bundle_pack(archive, pack)
    payload.seek(0)
    with tarfile.open(fileobj=payload) as archive:
        archive.extractall(tmp_path / "out", filter="data")
    imported = load_pack(tmp_path / "out/vision/bridge/pack.json")
    imported.validate()
    assert (Path(imported.runner).parent / "llama/llama-mtmd-cli").read_bytes() == b"native descendant"
    assert not (Path(imported.runner).parent / "unrelated-private.txt").exists()
    (worker / "llama/llama-mtmd-cli").write_bytes(b"tampered")
    with tarfile.open(fileobj=io.BytesIO(), mode="w") as archive, pytest.raises(ValueError, match="distribution changed"):
        bundle_pack(archive, dataclasses.replace(pack))
