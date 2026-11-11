import dataclasses
import json
from pathlib import Path

import pytest

from ocready.core import models, neural_packs


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
