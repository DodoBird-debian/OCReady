import json

from ocready.core.models import ModelPack, load_pack
from scripts.build_variant import json_pack_manifest
from scripts.variants import vision_presets


def test_swap_runtime_preserves_weights_prompt_limits_and_native_pack(tmp_path):
    assets = {}
    for name in ("native", "model.gguf", "projector.gguf", "json-worker"):
        path = tmp_path / name
        path.write_bytes(b"GGUF fixture")
        assets[name] = path
    pack = ModelPack("small", "Small English", str(assets["native"]), str(assets["model.gguf"]),
                     str(assets["projector.gguf"]), memory_mb=500, tokens=128, languages="eng", prompt="Read exact text.")
    manifest = tmp_path / "pack.json"
    original = json.dumps(pack.to_dict())
    manifest.write_text(original)
    swapped = load_pack(json_pack_manifest(manifest, assets["json-worker"]))
    assert manifest.read_text() == original
    assert swapped.id != pack.id and swapped.adapter == "json-cli-v1"
    assert swapped.runner == str(assets["json-worker"])
    for field in ("name", "model", "projector", "prompt", "memory_mb", "tokens", "max_pixels", "max_edge", "languages", "license", "source"):
        assert getattr(swapped, field) == getattr(pack, field)


def test_curated_studio_retains_both_vision_models_for_either_runtime():
    assert vision_presets("studio", "multimodal-json") == vision_presets("studio", "multimodal") == ["smol-q4", "qwen3"]
    assert vision_presets("everyday", "multimodal-json") == ["smol-q4"]
    assert vision_presets("everyday", "multimodal") == ["smol"]
    assert not vision_presets("studio", "combined")
