import os
import sys
from pathlib import Path


def resource_root() -> Path:
    # Nuitka onefile sets __file__ inside its private extracted payload.
    return Path(__file__).resolve().parents[2]


def runtime_root() -> Path:
    override = os.environ.get("OCREADY_RUNTIME")
    return Path(override).expanduser().resolve() if override else resource_root() / "runtime"


def config_root() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming")))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
    return base / "OCReady"
