import io
import json
import tarfile
from pathlib import Path

import pytest

from ocready.core import paths
from ocready.core.models import ModelPack, load_pack
from scripts.bundle_models import bundle_neural_pack, bundle_pack
from scripts.smoke_binary import embedded_selections


def test_combined_binary_validation_covers_every_embedded_method_and_model():
    profile = {"methods": ["tesseract-fast", "tesseract-best", "vision", "neural"],
               "embedded_models": [{"id": "small"}, {"id": "large"}], "embedded_neural": [{"id": "bilingual"}]}
    assert embedded_selections(profile) == [("tesseract-fast", ""), ("tesseract-best", ""),
                                            ("vision", "small"), ("vision", "large"), ("neural", "bilingual")]


def test_embedded_model_pack_contains_relative_paths_and_real_assets(tmp_path):
    runner = tmp_path / "llama-mtmd-cli"
    runner.write_text("test executable")
    runner.chmod(0o755)
    model, projector = (tmp_path / name for name in ("model.gguf", "mmproj.gguf"))
    model.write_bytes(b"GGUFmodel")
    projector.write_bytes(b"GGUFprojector")
    pack = ModelPack("tiny", "Tiny", str(runner), str(model), str(projector), memory_mb=500, languages="eng")
    payload = tmp_path / "payload.tar.gz"
    with tarfile.open(payload, "w:gz") as archive:
        metadata = bundle_pack(archive, pack)
    destination = tmp_path / "extracted"
    with tarfile.open(payload) as archive:
        archive.extractall(destination, filter="data")
    imported = load_pack(destination / "vision" / "tiny" / "pack.json")
    imported.validate()
    assert imported.bundled
    assert imported.languages == "eng"
    assert Path(imported.model).read_bytes() == model.read_bytes()
    assert metadata["model_sha256"]


def test_runtime_archive_rejects_escaping_links(tmp_path, monkeypatch):
    monkeypatch.delenv("OCREADY_RUNTIME", raising=False)
    monkeypatch.setattr(paths, "resource_root", lambda: tmp_path)
    with tarfile.open(tmp_path / "runtime-bundle.tar.gz", "w:gz") as archive:
        info = tarfile.TarInfo("evil")
        info.type, info.linkname = tarfile.SYMTYPE, "../../outside"
        archive.addfile(info)
    with pytest.raises(RuntimeError, match="Unsafe link"):
        paths.runtime_root()
    assert not (tmp_path / "runtime").exists()


def test_runtime_archive_preserves_safe_shared_library_aliases(tmp_path, monkeypatch):
    monkeypatch.delenv("OCREADY_RUNTIME", raising=False)
    monkeypatch.setattr(paths, "resource_root", lambda: tmp_path)
    with tarfile.open(tmp_path / "runtime-bundle.tar.gz", "w:gz") as archive:
        data = b"shared library"
        info = tarfile.TarInfo("lib/engine.so.1")
        info.size = len(data)
        archive.addfile(info, io.BytesIO(data))
        alias = tarfile.TarInfo("lib/engine.so")
        alias.type, alias.linkname = tarfile.LNKTYPE, "lib/engine.so.1"
        archive.addfile(alias)
    result = paths.runtime_root()
    assert (result / "lib/engine.so").read_bytes() == b"shared library"


def test_late_unsafe_runtime_entry_removes_partial_staging(tmp_path, monkeypatch):
    monkeypatch.delenv("OCREADY_RUNTIME", raising=False)
    monkeypatch.setattr(paths, "resource_root", lambda: tmp_path)
    with tarfile.open(tmp_path / "runtime-bundle.tar.gz", "w:gz") as archive:
        info = tarfile.TarInfo("lib/valid.so")
        info.size = 4
        archive.addfile(info, io.BytesIO(b"safe"))
        unsafe = tarfile.TarInfo("escape")
        unsafe.type, unsafe.linkname = tarfile.SYMTYPE, "../../outside"
        archive.addfile(unsafe)
    with pytest.raises(RuntimeError, match="Unsafe link"):
        paths.runtime_root()
    assert not (tmp_path / "runtime").exists()
    assert not (tmp_path / "runtime-extract").exists()
    assert not (tmp_path.parent / "outside").exists()


def test_vision_only_method_registry_can_be_selected(tmp_path, monkeypatch):
    profile = {"edition": "studio", "available_editions": ["studio"], "methods": ["vision"]}
    (tmp_path / "build-manifest.json").write_text(json.dumps(profile))
    monkeypatch.setattr(paths, "resource_root", lambda: tmp_path)
    assert paths.build_profile()["methods"] == ["vision"]


def test_neural_bundle_preserves_nested_runtime_and_line_metadata(tmp_path):
    from ocready.core.neural_packs import NeuralPack, load_neural_pack
    worker = tmp_path / "worker"
    worker.mkdir()
    runner = worker / "runner"
    runner.write_bytes(b"executable")
    (worker / "nested").mkdir()
    (worker / "nested/library.so").write_bytes(b"runtime library")
    from scripts.provenance import file_sha256
    metadata = {"protocol": 1, "files": {p.relative_to(worker).as_posix(): file_sha256(p)
                                         for p in worker.rglob("*") if p.is_file()}}
    (worker / "neural-build.json").write_text(json.dumps(metadata))
    (worker / "private-unrelated.txt").write_text("not part of the built worker")
    assets = []
    for name in ("detector.onnx", "recognizer.onnx", "dictionary.txt"):
        path = tmp_path / name
        path.write_text("a\nb\n")
        assets.append(str(path))
    pack = NeuralPack("local", "Neural pack", str(runner), *assets)
    payload = tmp_path / "payload.tar.gz"
    with tarfile.open(payload, "w:gz") as archive:
        metadata = bundle_neural_pack(archive, pack)
    with tarfile.open(payload) as archive:
        archive.extractall(tmp_path / "out", filter="data")
    extracted = load_neural_pack(tmp_path / "out/neural/local/pack.json")
    extracted.validate()
    assert extracted.bundled
    assert metadata["geometry"] == "line"
    assert (Path(extracted.runner).parent / "nested/library.so").read_bytes() == b"runtime library"
    assert not (Path(extracted.runner).parent / "private-unrelated.txt").exists()

