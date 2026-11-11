"""Stable optional runners kept separately from managed, extracted model assets."""
import json
import re
from pathlib import Path

from ocready.core.paths import config_root, runtime_root
from ocready.core.types import OCRError

NEURAL_ADAPTER = "neural-json-v1"


def _key(kind: str, pack_id: str, adapter: str) -> str:
    valid = adapter in {"llama.cpp", "json-cli-v1"} if kind == "vision" else kind == "neural" and adapter == NEURAL_ADAPTER
    if not valid or not re.fullmatch(r"[a-zA-Z0-9_-]{1,60}", pack_id):
        raise OCRError("Choose a supported local model and inference runtime for the CUDA helper.")
    return f"{kind}:{adapter}:{pack_id}"


def _read() -> dict[str, str]:
    path = config_root() / "cuda-helpers.json"
    try:
        if path.stat().st_size > 256_000:
            return {}
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or type(data.get("schema")) is not int or data["schema"] != 1:
            return {}
        helpers = data.get("helpers")
        if not isinstance(helpers, dict):
            return {}
        return {key: value for key, value in list(helpers.items())[:80]
                if isinstance(key, str) and isinstance(value, str) and 0 < len(value) <= 4096
                and Path(value).is_absolute()}
    except (OSError, ValueError):
        return {}


def cuda_helper(kind: str, pack_id: str, adapter: str) -> str:
    # Keep missing helpers visible in Settings; inference can still use CPU.
    try:
        return _read().get(_key(kind, pack_id, adapter), "")
    except OCRError:
        return ""


def save_cuda_helper(kind: str, pack_id: str, adapter: str, value: str) -> None:
    key = _key(kind, pack_id, adapter)
    helpers = _read()
    if value.strip():
        program = Path(value).expanduser().resolve()
        if not program.is_file():
            raise OCRError("The CUDA runner does not exist. Choose its executable or clear the optional helper.")
        if program.is_relative_to(runtime_root().resolve()):
            raise OCRError("Choose a CUDA runner outside the application's managed runtime so it remains available after restarting.")
        if len(str(program)) > 4096:
            raise OCRError("Choose a CUDA runner with a shorter file path.")
        if key not in helpers and len(helpers) >= 80:
            raise OCRError("Too many optional CUDA helpers are configured.")
        helpers[key] = str(program)
    else:
        helpers.pop(key, None)
    path = config_root() / "cuda-helpers.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps({"schema": 1, "helpers": helpers}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
