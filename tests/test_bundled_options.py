import dataclasses
import json
from pathlib import Path

import pytest

from ocready.core import cuda_helpers, models, neural_packs
from ocready.core.types import OCRError


def prepare_bundle(root, kind, *, adapter="llama.cpp"):
    folder = root / kind / "builtin"
    folder.mkdir(parents=True)
    names = ("runner", "model", "projector") if kind == "vision" else ("runner", "detector", "recognizer", "dictionary")
    assets = []
    for name in (*names, "cuda_runner"):
        (folder / name).write_bytes(b"GGUFdata\n")
        assets.append(str(folder / name))
    pack = (models.ModelPack("builtin", "Built in", *assets[:3], cuda_runner=assets[-1], adapter=adapter, memory_mb=500) if kind == "vision"
            else neural_packs.NeuralPack("builtin", "Built in", *assets[:4], cuda_runner=assets[-1]))
    record = pack.to_dict()
    for name in (*names, "cuda_runner"):
        record[name] = Path(record[name]).name
    (folder / "pack.json").write_text(json.dumps(record))
    return pack


@pytest.mark.parametrize("kind", ["vision", "neural"])
def test_builtin_options_follow_fresh_extraction_paths_and_survive_other_editions(tmp_path, monkeypatch, kind):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "config"))
    module = models if kind == "vision" else neural_packs
    load = models.load_packs if kind == "vision" else neural_packs.load_neural_packs
    save = models.save_packs if kind == "vision" else neural_packs.save_neural_packs
    runtime = {"path": tmp_path / "first-extraction"}
    monkeypatch.setattr(module, "runtime_root", lambda: runtime["path"])
    monkeypatch.setattr(module, "build_profile", lambda: {"methods": [kind]})
    def prepare(root):
        folder = root / kind / "builtin"
        folder.mkdir(parents=True)
        names = ("runner", "model", "projector") if kind == "vision" else ("runner", "detector", "recognizer", "dictionary")
        paths = []
        for name in names:
            path = folder / name
            path.write_bytes(b"GGUFdata\n")
            paths.append(str(path))
        pack = (models.ModelPack("builtin", "Built in", *paths, memory_mb=500) if kind == "vision"
                else neural_packs.NeuralPack("builtin", "Built in", *paths))
        values = pack.to_dict()
        for name in names:
            values[name] = Path(values[name]).name
        (folder / "pack.json").write_text(json.dumps(values))
    prepare(runtime["path"])
    original = load()[0]
    assert original.bundled
    save([dataclasses.replace(original, memory_mb=650)])
    filename = "models.json" if kind == "vision" else "neural-models.json"
    settings = module.config_root() / filename
    assert "first-extraction" not in settings.read_text()
    runtime["path"] = tmp_path / "second-extraction"
    prepare(runtime["path"])
    restored = load()[0]
    assert restored.memory_mb == 650
    assert "second-extraction" in restored.runner
    restored.validate()
    runtime["path"] = tmp_path / "edition-without-this-model"
    assert not load()
    save([])
    assert json.loads(settings.read_text())[0]["memory_mb"] == 650
    runtime["path"] = tmp_path / "second-extraction"
    assert load()[0].memory_mb == 650


@pytest.mark.parametrize("kind", ["vision", "neural"])
def test_optional_helpers_follow_model_identity_without_persisting_extracted_assets(tmp_path, monkeypatch, kind):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "config"))
    module = models if kind == "vision" else neural_packs
    load = models.load_packs if kind == "vision" else neural_packs.load_neural_packs
    save = models.save_packs if kind == "vision" else neural_packs.save_neural_packs
    adapter = "llama.cpp" if kind == "vision" else cuda_helpers.NEURAL_ADAPTER
    runtime = {"path": tmp_path / "first-extraction"}
    monkeypatch.setattr(module, "runtime_root", lambda: runtime["path"])
    monkeypatch.setattr(cuda_helpers, "runtime_root", lambda: runtime["path"])
    monkeypatch.setattr(module, "build_profile", lambda: {"methods": [kind]})
    original = prepare_bundle(runtime["path"], kind)
    external = tmp_path / "مسرع CUDA"
    external.write_bytes(b"compatible external helper")
    cuda_helpers.save_cuda_helper(kind, "builtin", adapter, str(external))
    selected = load()[0]
    assert selected.cuda_runner == str(external)
    selected.validate()
    save([dataclasses.replace(selected, memory_mb=650)])
    all_config = "".join(path.read_text(encoding="utf-8") for path in module.config_root().glob("*.json"))
    assert "first-extraction" not in all_config
    helper_record = json.loads((module.config_root() / "cuda-helpers.json").read_text(encoding="utf-8"))
    assert str(external) in helper_record["helpers"].values()
    runtime["path"] = tmp_path / "fresh-extraction"
    fresh = prepare_bundle(runtime["path"], kind)
    restored = load()[0]
    assert restored.runner == fresh.runner and restored.runner != original.runner
    assert restored.cuda_runner == str(external) and restored.memory_mb == 650
    external.unlink()
    assert load()[0].cuda_runner == str(external)
    with pytest.raises(OCRError):
        restored.validate()
    restored.validate(require_cuda=False)
    # Invalid choices leave the last saved helper unchanged.
    helper_settings = module.config_root() / "cuda-helpers.json"
    before = helper_settings.read_bytes()
    for rejected in (str(external), fresh.runner):
        with pytest.raises(OCRError):
            cuda_helpers.save_cuda_helper(kind, "builtin", adapter, rejected)
        assert helper_settings.read_bytes() == before
    runtime["path"] = tmp_path / "edition-without-model"
    assert not load()
    save([])
    assert cuda_helpers.cuda_helper(kind, "builtin", adapter) == str(external)
    runtime["path"] = Path(fresh.runner).parents[2]
    cuda_helpers.save_cuda_helper(kind, "builtin", adapter, "")
    assert load()[0].cuda_runner == fresh.cuda_runner
    load()[0].validate()


def test_helpers_do_not_cross_runtime_adapters_or_model_families(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "config"))
    monkeypatch.setattr(cuda_helpers, "runtime_root", lambda: tmp_path / "managed")
    paths = []
    keys = [("vision", "builtin", "llama.cpp"), ("vision", "builtin", "json-cli-v1"),
            ("neural", "builtin", cuda_helpers.NEURAL_ADAPTER), ("vision", "other", "llama.cpp")]
    for index, key in enumerate(keys):
        path = tmp_path / f"helper-{index}"
        path.write_bytes(b"worker")
        paths.append(str(path))
        cuda_helpers.save_cuda_helper(*key, str(path))
    assert [cuda_helpers.cuda_helper(*key) for key in keys] == paths
    cuda_helpers.save_cuda_helper(*keys[1], "")
    assert [cuda_helpers.cuda_helper(*key) for key in keys] == [paths[0], "", *paths[2:]]
