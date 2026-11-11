"""Shared curated-build names; custom combinations still use scripts.build."""

MODEL_VARIANTS = ("neural", "combined", "multimodal", "multimodal-json")
VISION_VARIANTS = frozenset({"multimodal", "multimodal-json"})


def vision_presets(edition: str, variant: str) -> list[str]:
    if variant not in VISION_VARIANTS:
        return []
    if edition == "studio":
        return ["smol-q4", "qwen3"]
    return ["smol-q4" if variant == "multimodal-json" else "smol"]
