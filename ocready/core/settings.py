import json
from pathlib import Path

from ocready.core.paths import config_root


def load_settings(path: Path | None = None) -> dict:
    path = path or config_root() / "settings.json"
    try:
        if path.stat().st_size > 100_000:
            return {}
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_settings(data: dict, path: Path | None = None) -> None:
    path = path or config_root() / "settings.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps({"schema": 1, **data}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
