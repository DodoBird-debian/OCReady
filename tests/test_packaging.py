import io
import json
import tarfile
from pathlib import Path

import pytest

from ocready.core import paths
from ocready.core.models import ModelPack, load_pack
from scripts.bundle_models import bundle_pack


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


def test_vision_only_method_registry_can_be_selected(tmp_path, monkeypatch):
    profile = {"edition": "studio", "available_editions": ["studio"], "methods": ["vision"]}
    (tmp_path / "build-manifest.json").write_text(json.dumps(profile))
    monkeypatch.setattr(paths, "resource_root", lambda: tmp_path)
    assert paths.build_profile()["methods"] == ["vision"]

