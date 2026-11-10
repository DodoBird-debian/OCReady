import os
import sys
import tarfile
import threading
from pathlib import Path

_runtime_lock = threading.Lock()


def resource_root() -> Path:
    # Nuitka onefile sets __file__ inside its private extracted payload.
    return Path(__file__).resolve().parents[2]


def runtime_root() -> Path:
    override = os.environ.get("OCREADY_RUNTIME")
    if override:
        return Path(override).expanduser().resolve()
    target = resource_root() / "runtime"
    bundle = resource_root() / "runtime-bundle.tar.gz"
    if not target.exists() and bundle.is_file():
        with _runtime_lock:
            if not target.exists():
                staging = target.with_name("runtime-extract")
                staging.mkdir(parents=True, exist_ok=True)
                with tarfile.open(bundle, "r:gz") as archive:
                    for member in archive.getmembers():
                        path = Path(member.name)
                        if path.is_absolute() or ".." in path.parts or not (member.isfile() or member.isdir() or member.islnk() or member.issym()):
                            raise RuntimeError("Unsafe path in bundled OCR runtime.")
                        if member.islnk() or member.issym():
                            link = Path(member.linkname)
                            if link.is_absolute() or ".." in link.parts:
                                raise RuntimeError("Unsafe link in bundled OCR runtime.")
                    archive.extractall(staging, filter="data")
                staging.rename(target)
    return target


def build_profile() -> dict:
    import json
    path = resource_root() / "build-manifest.json"
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"edition": "pocket", "available_editions": ["pocket", "everyday", "studio"],
            "methods": ["tesseract-fast", "tesseract-best", "vision"]}


def config_root() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming")))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
    return base / "OCReady"
